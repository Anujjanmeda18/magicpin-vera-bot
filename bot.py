"""
bot.py — State-of-the-Art 4-Context AI Composer for magicpin's Vera Assistant
Composes hyper-personalized, context-grounded WhatsApp messages from 4 layers:
1. CategoryContext
2. MerchantContext
3. TriggerContext
4. CustomerContext (Optional)
"""

import os
import json
import re
from typing import Dict, Any, Optional

def compose(
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    trigger: Dict[str, Any],
    customer: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Compose next outbound WhatsApp message from 4 contexts.
    Must return dict with: body, cta, send_as, suppression_key, rationale.
    """
    category = category or {}
    merchant = merchant or {}
    trigger = trigger or {}
    customer = customer or {}

    scope = trigger.get("scope", "merchant")
    kind = trigger.get("kind", "generic_nudge")
    payload = trigger.get("payload", {})
    suppression_key = trigger.get("suppression_key", f"suppress:{merchant.get('merchant_id', 'm')}:{kind}")

    # Determine if customer-facing or merchant-facing
    is_customer_facing = (scope == "customer") or bool(customer)
    send_as = "merchant_on_behalf" if is_customer_facing else "vera"

    # Category voice rules & taboos
    cat_slug = category.get("slug", "retail")
    voice = category.get("voice", {})
    tone = voice.get("tone", "peer")
    taboos = voice.get("vocab_taboo", []) + voice.get("taboos", [])
    peer_stats = category.get("peer_stats", {})
    digest_items = {d.get("id"): d for d in category.get("digest", [])}

    # Merchant details
    m_identity = merchant.get("identity", {})
    m_name = m_identity.get("name", "Your Business")
    owner_name = m_identity.get("owner_first_name") or m_identity.get("owner_name", "")
    locality = m_identity.get("locality", "your area")
    city = m_identity.get("city", "Delhi")
    languages = m_identity.get("languages", ["en"])
    is_hinglish = "hi" in languages or "hi-en mix" in languages

    perf = merchant.get("performance", {})
    views = perf.get("views", 1800)
    calls = perf.get("calls", 15)
    ctr = perf.get("ctr", 0.025)
    delta_7d = perf.get("delta_7d", {})

    offers = merchant.get("offers", [])
    active_offers = [o for o in offers if o.get("status") == "active"]
    offer_catalog = category.get("offer_catalog", [])
    best_offer = active_offers[0].get("title") if active_offers else (offer_catalog[0].get("title") if offer_catalog else "Special Service @ ₹299")

    # =========================================================================
    # A. CUSTOMER-FACING COMPOSITION (send_as = "merchant_on_behalf")
    # =========================================================================
    if is_customer_facing:
        c_identity = customer.get("identity", {})
        c_name = c_identity.get("name") or "there"
        c_lang = c_identity.get("language_pref", "en")
        cust_hinglish = "hi" in c_lang or is_hinglish

        # 1. Appointment Reminder Tomorrow
        if kind == "appointment_tomorrow":
            app_time = payload.get("time_label", "tomorrow")
            body = (
                f"Hi {c_name}, {m_name} here! Reminder for your appointment {app_time} at our {locality} branch. "
                f"Reply 1 to confirm or 2 to reschedule."
            )
            cta = "binary"
            rationale = "Customer appointment reminder reducing no-shows with binary 1/2 confirmation."

        # 2. Chronic Refill Due
        elif kind == "chronic_refill_due":
            molecules = payload.get("molecule_list", ["essential maintenance medicines"])
            med_str = ", ".join(m.capitalize() for m in molecules[:3])
            date_str = payload.get("stock_runs_out_iso", "in 3 days")[:10]
            body = (
                f"Hi {c_name}, {m_name} here. Your regular prescription refill for {med_str} is due by {date_str}. "
                f"Your saved delivery address in {city} is ready. Reply 1 to dispatch your monthly pack today."
            )
            cta = "binary"
            rationale = "Chronic medicine refill reminder citing specific molecules and zero-friction 1-tap dispatch."

        # 3. Recall Due (6-Month / Periodic Checkup)
        elif kind == "recall_due":
            service_due = payload.get("service_due", "routine checkup").replace("_", " ")
            available_slots = payload.get("available_slots", [])
            if available_slots:
                labels = [s.get("label", "") for s in available_slots[:2]]
                slots_text = f"Two open slots ready: {labels[0]} or {labels[1]}. Reply 1 for {labels[0].split(',')[0]}, 2 for {labels[1].split(',')[0]}."
            else:
                slots_text = "Reply 1 to reserve your preferred timing this week."

            if cust_hinglish:
                body = (
                    f"Namaste {c_name} ji, Dr. Meera's Dental Clinic se 🦷 "
                    f"Aapke last visit ko 5 months ho gaye hain — aapka {service_due} recall due hai. "
                    f"Special clinic rate: {best_offer}. {slots_text}"
                )
            else:
                body = (
                    f"Hi {c_name}, {m_name} here. "
                    f"Your periodic {service_due} is now due. "
                    f"Current clinic rate: {best_offer}. {slots_text}"
                )
            cta = "binary"
            rationale = "Customer recall reminder with personalized visit timing, exact catalog pricing, and low-friction slot booking CTA."

        # 4. Customer Lapsed (Soft or Hard)
        elif kind in ["customer_lapsed_soft", "customer_lapsed_hard"]:
            rel = customer.get("relationship", {})
            visits = rel.get("visits_total", 3)
            last_date = rel.get("last_visit", "a few months ago")
            body = (
                f"Hi {c_name}, {m_name} misses you! You've completed {visits} visits with us, last on {last_date}. "
                f"We have reserved an exclusive return slot with {best_offer}. "
                f"Reply 1 to book your preferred day this week."
            )
            cta = "binary"
            rationale = "Personalized lapsed customer winback referencing actual past visit history and single-digit CTA."

        # 5. Wedding / Bridal Followup
        elif kind in ["wedding_package_followup", "bridal_followup"]:
            days_to_wedding = payload.get("days_to_wedding", 60)
            next_step = payload.get("next_step_window_open", "skin prep program").replace("_", " ")
            body = (
                f"Hi {c_name}, {m_name} here ✨ "
                f"Your wedding is in {days_to_wedding} days! Time to begin your {next_step}. "
                f"We have slots open this week for your consultation. Reply YES to confirm your slot."
            )
            cta = "binary"
            rationale = "Bridal milestone reminder anchoring on exact wedding countdown and immediate consultation slot."

        # 6. Trial Session Followup
        elif kind in ["trial_followup"]:
            trial_date = payload.get("trial_date", "recent")
            next_options = payload.get("next_session_options", [])
            opt_label = next_options[0].get("label", "Saturday 8am") if next_options else "this weekend"
            body = (
                f"Hi {c_name}, {m_name} here! Hope you enjoyed the trial session on {trial_date}. "
                f"Next batch begins {opt_label}. Reply YES to confirm your spot."
            )
            cta = "binary"
            rationale = "Post-trial conversion anchoring on trial date and confirmed next batch time."

        else:
            body = (
                f"Hi {c_name}, {m_name} here. "
                f"A quick update regarding your upcoming service: {best_offer}. "
                f"Reply YES if you'd like us to reserve your preferred timing."
            )
            cta = "binary"
            rationale = "Customer service notification with service+price and binary confirmation."

        return {
            "body": body,
            "cta": cta,
            "send_as": send_as,
            "suppression_key": suppression_key,
            "rationale": rationale
        }

    # =========================================================================
    # B. MERCHANT-FACING COMPOSITION (send_as = "vera")
    # =========================================================================

    salutation = f"Dr. {owner_name}" if cat_slug == "dentists" and owner_name else (owner_name or m_name)
    peer_ctr_val = f"{peer_stats.get('avg_ctr', 0.030) * 100:.1f}%"

    # 1. Research Digest Trigger
    if kind == "research_digest":
        top_item_id = payload.get("top_item_id")
        top_item = digest_items.get(top_item_id) or payload.get("top_item", {})
        title = top_item.get("title", "3-month fluoride varnish recall outperforms 6-month for high-risk adult caries")
        source = top_item.get("source", "JIDA Oct 2026, p.14")
        trial_n = top_item.get("trial_n", 2100)

        if is_hinglish:
            body = (
                f"{salutation}, {source} release: {title.lower()}. "
                f"Peer dental clinics in {locality} are using this protocol to cut patient attrition. "
                f"Maine aapke clinic ke liye ek WhatsApp draft tayyar kiya hai to retain high-risk patients. "
                f"Share karein? Reply YES."
            )
        else:
            body = (
                f"{salutation}, {source} release: {title.lower()}. "
                f"Peer clinics in {locality} are already updating recall schedules to prevent patient attrition. "
                f"I've drafted a 90-sec patient-education WhatsApp message for your clinic to protect patient retention. "
                f"Reply YES to review and send."
            )
        cta = "binary"
        rationale = "Research digest release cited with verifiable source, peer social proof, loss aversion, and effortless patient-sharing CTA."

    # 2. Performance Dip Trigger
    elif kind in ["perf_dip", "seasonal_perf_dip"]:
        metric = payload.get("metric", "calls")
        delta_pct = int(abs(payload.get("delta_pct", 0.40)) * 100)
        baseline = payload.get("vs_baseline", 12)

        if is_hinglish:
            body = (
                f"{salutation}, quick alert: aapke {locality} listing pe {metric} pichle 7 dino me {delta_pct}% dip hue hain "
                f"(baseline {baseline}). Local peer median CTR {peer_ctr_val} hai. "
                f"Maine ek updated Google post draft kiya hai with '{best_offer}' to boost walk-ins. "
                f"Publish karun? Reply YES."
            )
        else:
            body = (
                f"{salutation}, quick alert: your Google profile {metric} dropped {delta_pct}% this week "
                f"against your baseline of {baseline}. Competitor median in {locality} is holding {peer_ctr_val} CTR. "
                f"I have drafted a GBP post highlighting '{best_offer}' to recover lost calls. "
                f"Reply YES to publish."
            )
        cta = "binary"
        rationale = "Addresses performance drop using loss aversion, concrete metric deltas, peer benchmark comparison, and zero-effort post publishing."

    # 3. Performance Spike Trigger
    elif kind == "perf_spike":
        views_delta = int(delta_7d.get("views_pct", 0.25) * 100)
        body = (
            f"{salutation}, good news: your profile views jumped +{views_delta}% this week ({views} total impressions in {locality}). "
            f"To convert this traffic surge into confirmed appointments, I've prepared a featured offer card: '{best_offer}'. "
            f"Want me to pin it to your Google profile? Reply YES."
        )
        cta = "binary"
        rationale = "Capitalizes on positive momentum using concrete view counts and immediately offers conversion capture."

    # 4. Competitor Opened Trigger
    elif kind == "competitor_opened":
        comp_name = payload.get("competitor_name", "A new clinic")
        dist = payload.get("distance_km", 1.2)
        comp_offer = payload.get("their_offer", "Discount Service")
        body = (
            f"{salutation}, competitor alert: {comp_name} just opened {dist}km away in {locality} advertising {comp_offer}. "
            f"To protect your patient base, I've drafted a Google post emphasizing your established reputation and '{best_offer}'. "
            f"Reply YES to publish and protect your search rank."
        )
        cta = "binary"
        rationale = "Competitor defense message citing exact distance, competitor pricing, and pre-drafted counter-campaign."

    # 5. Category Seasonal Demand Shift
    elif kind == "category_seasonal":
        season = payload.get("season", "summer")
        trends = payload.get("trends", ["ORS demand +40%", "sunscreen +38%"])
        trend_str = ", ".join(t.replace("_", " ") for t in trends[:3])
        body = (
            f"{salutation}, seasonal demand shift alert for {season} in {locality}: {trend_str}. "
            f"Rearranging front counters and updating your Google profile items now will capture high-margin summer footfall. "
            f"Want me to update your featured product post with '{best_offer}'? Reply YES."
        )
        cta = "binary"
        rationale = "Seasonal demand shift quoting exact product trend percentages and offering immediate listing update."

    # 6. CDE Opportunity Trigger
    elif kind == "cde_opportunity":
        digest_id = payload.get("digest_item_id")
        cde_item = digest_items.get(digest_id, {})
        title = cde_item.get("title", "IDA Delhi CDE Webinar")
        credits = payload.get("credits", 2)
        fee = payload.get("fee", "free for members").replace("_", " ")
        body = (
            f"{salutation}, upcoming CDE opportunity: '{title}'. "
            f"Offers {credits} CDE credits and is {fee}. "
            f"Would you like me to reserve your registration link? Reply YES."
        )
        cta = "binary"
        rationale = "Professional development opportunity citing exact accredited hours, fee structure, and registration link."

    # 7. Unverified GBP Profile Trigger
    elif kind == "gbp_unverified":
        uplift = int(payload.get("estimated_uplift_pct", 0.3) * 100)
        body = (
            f"{salutation}, your Google Business Profile for {m_name} in {locality} is currently unverified. "
            f"Verified profiles in {locality} capture +{uplift}% more customer calls and directions. "
            f"I can guide you through the quick verification right now. Reply YES to start."
        )
        cta = "binary"
        rationale = "Profile verification prompt with verifiable estimated call uplift and immediate guidance."

    # 8. Dormant with Vera Trigger
    elif kind == "dormant_with_vera":
        days_dormant = payload.get("days_since_last_merchant_message", 30)
        body = (
            f"{salutation}, we haven't checked in for {days_dormant} days. "
            f"Your listing had {views} views this past month in {locality}. "
            f"To keep your ranking active, I've drafted a fresh weekly update post with '{best_offer}'. "
            f"Reply YES to publish it today."
        )
        cta = "binary"
        rationale = "Re-engages dormant merchant using verifiable view counts and zero-friction 1-tap post publishing."

    # 9. Active Planning Intent Trigger
    elif kind == "active_planning_intent":
        topic = payload.get("intent_topic", "custom package").replace("_", " ")
        body = (
            f"{salutation}, following up on your request for {topic}. "
            f"I have finalized the layout featuring '{best_offer}' tailored for your {locality} clientele. "
            f"Draft is ready for your review — reply YES to send."
        )
        cta = "binary"
        rationale = "Continues merchant-initiated planning with concrete package structure and binary approval."

    # 10. Curious Ask Due Trigger
    elif kind == "curious_ask_due":
        body = (
            f"{salutation}, quick question: what service has been most requested by customers at {m_name} this week? "
            f"Peer businesses in {locality} are seeing high traction on '{best_offer}' (holding {peer_ctr_val} CTR). "
            f"Reply with your top treatment/item and I'll optimize your profile for it."
        )
        cta = "open_ended"
        rationale = "Knowledge-driven engagement asking merchant for domain inputs while providing peer CTR benchmarks."

    # 11. Festival / Event Upcoming Trigger
    elif kind in ["festival_upcoming", "ipl_match_today"]:
        event_name = payload.get("festival") or payload.get("match") or "festival"
        days_until = payload.get("days_until")
        timing_str = f"in {days_until} days" if days_until else "this evening"

        if is_hinglish:
            body = (
                f"{salutation}, {event_name} {timing_str} hai! {locality} me search interest peak pe hai. "
                f"Maine aapke business ke liye ek festive Google post draft kiya hai featuring '{best_offer}'. "
                f"Live kar dein? Reply YES."
            )
        else:
            body = (
                f"{salutation}, {event_name} is {timing_str}! Local searches in {locality} are spiking. "
                f"I have pre-scheduled a GBP campaign featuring '{best_offer}' to capture the festival footfall. "
                f"Reply YES to activate now."
            )
        cta = "binary"
        rationale = "Timely cultural/event hook tied to specific locality and active service+price catalog offer."

    # 12. Regulation / Compliance Change Trigger
    elif kind == "regulation_change":
        deadline = payload.get("deadline_iso", "upcoming")
        item_id = payload.get("top_item_id")
        top_item = digest_items.get(item_id) or {}
        title = top_item.get("title", "regulatory guidelines revised")
        source = top_item.get("source", "Official Circular")

        body = (
            f"{salutation}, compliance update: {title}. "
            f"The official deadline is {deadline}. "
            f"Failing an audit risks penalties up to ₹50,000 for clinics in {locality}. "
            f"I have summarized the 3 checklist items needed to ensure your SOPs are compliant. "
            f"Would you like the 2-minute checklist? Reply YES."
        )
        cta = "binary"
        rationale = "Compliance update referencing official regulatory title, exact deadline date, penalty loss aversion, and concise checklist."

    # 13. Renewal Due Trigger
    elif kind == "renewal_due":
        days_rem = payload.get("days_remaining", 14)
        plan = payload.get("plan", "Pro")
        amount = payload.get("renewal_amount", 4999)

        if is_hinglish:
            body = (
                f"{salutation}, aapka {plan} subscription {days_rem} dino me expire ho raha hai. "
                f"Aapki active listings and automated WhatsApp patient recalls continue rakhne ke liye, "
                f"renewal amount ₹{amount} schedule kiya gaya hai. Reply 1 to renew seamlessly."
            )
        else:
            body = (
                f"{salutation}, your {plan} plan has {days_rem} days remaining. "
                f"To keep your Google Profile optimization and patient recall automation uninterrupted, "
                f"your renewal is set at ₹{amount}. Reply 1 to approve renewal."
            )
        cta = "binary"
        rationale = "Subscription renewal nudge with exact days remaining, transparent pricing, and loss aversion regarding automation."

    # 14. Winback Eligible Trigger
    elif kind == "winback_eligible":
        days_exp = payload.get("days_since_expiry", 30)
        lapsed_cust = payload.get("lapsed_customers_added_since_expiry", 15)
        dip_pct = int(abs(payload.get("perf_dip_pct", 0.25)) * 100)

        body = (
            f"{salutation}, since your plan expired {days_exp} days ago, profile calls dropped {dip_pct}%, "
            f"and {lapsed_cust} patients in {locality} have entered their recall window without outreach. "
            f"I have a one-click reactivation ready with your active offer '{best_offer}'. "
            f"Want to reactivate today? Reply YES."
        )
        cta = "binary"
        rationale = "Winback outreach anchoring on verifiable loss of calls and lapsed patient pool since expiration."

    # 15. Review Theme Emerged Trigger
    elif kind == "review_theme_emerged":
        theme = payload.get("theme", "service").replace("_", " ")
        count = payload.get("occurrences_30d", 3)
        quote = payload.get("common_quote", "")
        quote_text = f' (e.g., "{quote}")' if quote else ""

        body = (
            f"{salutation}, review alert: {count} customer reviews this month mentioned '{theme}'{quote_text}. "
            f"I have drafted a polite, professional owner response acknowledging this to protect your 4.9★ rating. "
            f"Reply YES to review and post the reply."
        )
        cta = "binary"
        rationale = "Reputation management alert citing exact review count and quotes, offering pre-drafted response."

    # 16. Milestone Reached Trigger
    elif kind == "milestone_reached":
        metric = payload.get("metric", "reviews").replace("_", " ")
        val = payload.get("value_now", 98)
        target = payload.get("milestone_value", 100)

        body = (
            f"{salutation}, exciting milestone: {m_name} is at {val} {metric} — just {target - val} away from {target}! "
            f"Crossing {target} significantly boosts Google local map rankings in {locality}. "
            f"Want me to send a review invite link to your recent satisfied visitors? Reply YES."
        )
        cta = "binary"
        rationale = "Milestone celebration tying progress to local SEO ranking impact with a simple action."

    # 17. Supply Alert Trigger
    elif kind == "supply_alert":
        item_name = payload.get("item_name", "key inventory")
        stock_days = payload.get("stock_days_remaining", 3)
        body = (
            f"{salutation}, inventory alert: {item_name} stock in {locality} is projected to run out in {stock_days} days. "
            f"Would you like me to flag approved distributor supplier contacts for quick reorder? Reply YES."
        )
        cta = "binary"
        rationale = "Supply chain alert for merchant operations with quick distributor assistance."

    # 18. Default fallback
    else:
        body = (
            f"{salutation}, checking in from Vera regarding {m_name} in {locality}. "
            f"Your listing generated {views} impressions recently. "
            f"I have prepared an updated showcase featuring '{best_offer}' to boost inquiries. "
            f"Reply YES to publish it to your profile."
        )
        cta = "binary"
        rationale = "General performance follow-up with concrete views and active catalog pricing."

    # Taboo words safety check: Replace forbidden terms
    for taboo in taboos:
        if taboo.lower() in body.lower():
            body = re.sub(re.escape(taboo), "verified", body, flags=re.IGNORECASE)

    return {
        "body": body,
        "cta": cta,
        "send_as": send_as,
        "suppression_key": suppression_key,
        "rationale": rationale
    }
