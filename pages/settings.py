"""
pages/settings.py — Settings page.
All credentials saved locally to sme_data/settings.json
"""
import streamlit as st
from utils.storage import save_settings, load_settings


def show():
    st.markdown("<div class='hero'><div><h1>⚙️ Settings</h1>"
                "<p>Configure your business details and integrations</p></div></div>",
                unsafe_allow_html=True)

    cfg = load_settings()

    # ── Business ──────────────────────────────────────────────────────────────
    st.markdown("<div class='sec'>Business details</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        business = st.text_input("Business name",
                                  value=cfg.get("business", "My Business"))
    with c2:
        industry = st.selectbox("Industry",
                                 ["F&B", "Retail", "Services", "General"],
                                 index=["F&B", "Retail", "Services", "General"]
                                 .index(cfg.get("industry", "F&B")))

    # ── Email ─────────────────────────────────────────────────────────────────
    st.markdown("<div class='sec'>Email reports — Gmail</div>", unsafe_allow_html=True)

    st.markdown("""
    <div style='background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;
    padding:12px 16px;font-size:0.84rem;color:#0c4a6e;margin-bottom:12px;'>
    <strong>Setup (2 min):</strong><br>
    1. Enable 2FA at <a href='https://myaccount.google.com/security' target='_blank'>
    myaccount.google.com/security</a><br>
    2. Get app password at <a href='https://myaccount.google.com/apppasswords' target='_blank'>
    myaccount.google.com/apppasswords</a><br>
    3. Paste the 16-character code below
    </div>
    """, unsafe_allow_html=True)

    e1, e2 = st.columns(2)
    with e1:
        smtp_user = st.text_input("Your Gmail address",
                                   value=cfg.get("smtp_user", ""),
                                   placeholder="you@gmail.com")
    with e2:
        smtp_pass = st.text_input("Gmail app password",
                                   value=cfg.get("smtp_pass", ""),
                                   type="password",
                                   placeholder="xxxx xxxx xxxx xxxx")

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    st.markdown("<div class='sec'>WhatsApp reports — Twilio</div>",
                unsafe_allow_html=True)

    st.markdown("""
    <div style='background:#f0fdf4;border:1px solid #86efac;border-radius:10px;
    padding:12px 16px;font-size:0.84rem;color:#166534;margin-bottom:12px;'>
    <strong>Setup (5 min):</strong><br>
    1. Sign up free at <a href='https://twilio.com' target='_blank'>twilio.com</a>
    (free trial gives $15 credit)<br>
    2. Get a WhatsApp Sandbox number from Twilio Console<br>
    3. Copy Account SID, Auth Token, and WhatsApp number below<br>
    4. The recipient must send <strong>"join &lt;sandbox-keyword&gt;"</strong>
    to your Twilio number first
    </div>
    """, unsafe_allow_html=True)

    w1, w2 = st.columns(2)
    with w1:
        wa_to       = st.text_input("Recipient WhatsApp number",
                                     value=cfg.get("whatsapp_to", ""),
                                     placeholder="+6591234567")
        twilio_from = st.text_input("Twilio WhatsApp number",
                                     value=cfg.get("twilio_from", ""),
                                     placeholder="+1415XXXXXXX")
    with w2:
        twilio_sid   = st.text_input("Twilio Account SID",
                                      value=cfg.get("twilio_sid", ""),
                                      placeholder="ACxxxxxxxxxxxxxxxx")
        twilio_token = st.text_input("Twilio Auth Token",
                                      value=cfg.get("twilio_token", ""),
                                      type="password",
                                      placeholder="your auth token")

    # ── OpenAI ────────────────────────────────────────────────────────────────
    st.markdown("<div class='sec'>AI insights — OpenAI (optional)</div>",
                unsafe_allow_html=True)
    st.caption("Without a key, insights use rule-based analysis which is still sharp and specific.")
    openai_key = st.text_input("OpenAI API key",
                                value=cfg.get("openai_key", ""),
                                type="password",
                                placeholder="sk-...")

    # ── Save ──────────────────────────────────────────────────────────────────
    st.divider()
    if st.button("💾 Save settings", type="primary", use_container_width=False):
        new_cfg = dict(
            business=business, industry=industry,
            smtp_user=smtp_user, smtp_pass=smtp_pass,
            whatsapp_to=wa_to, twilio_sid=twilio_sid,
            twilio_token=twilio_token, twilio_from=twilio_from,
            openai_key=openai_key,
        )
        save_settings(new_cfg)

        # Update session state
        st.session_state.business     = business
        st.session_state.industry     = industry
        st.session_state.smtp_user    = smtp_user
        st.session_state.smtp_pass    = smtp_pass
        st.session_state.wa_to        = wa_to
        st.session_state.twilio_sid   = twilio_sid
        st.session_state.twilio_token = twilio_token
        st.session_state.twilio_from  = twilio_from
        st.session_state.openai_key   = openai_key

        st.success("✓ Settings saved! They'll be remembered next time you open the app.")

    # ── Test buttons ──────────────────────────────────────────────────────────
    st.markdown("<div class='sec'>Test your integrations</div>",
                unsafe_allow_html=True)

    t1, t2 = st.columns(2)
    test_to = st.text_input("Send test to this email/number",
                             placeholder="you@example.com or +6591234567")

    with t1:
        if st.button("📧 Send test email", use_container_width=True):
            from utils.sender import send_email
            import smtplib
            from email.mime.text import MIMEText
            if not smtp_user or not smtp_pass:
                st.error("Fill in Gmail settings above and save first.")
            elif not test_to:
                st.error("Enter a test email address above.")
            else:
                try:
                    msg = MIMEText("This is a test from your SME Co-Pilot app. Email is working!")
                    msg["Subject"] = "✓ SME Co-Pilot test email"
                    msg["From"]    = smtp_user
                    msg["To"]      = test_to
                    clean = smtp_pass.replace(" ", "")
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
                        srv.login(smtp_user, clean)
                        srv.sendmail(smtp_user, [test_to], msg.as_string())
                    st.success(f"✓ Test email sent to {test_to}")
                except smtplib.SMTPAuthenticationError:
                    st.error("Gmail auth failed — check your app password.")
                except Exception as e:
                    st.error(f"Failed: {e}")

    with t2:
        if st.button("💬 Send test WhatsApp", use_container_width=True):
            if not all([wa_to, twilio_sid, twilio_token, twilio_from]):
                st.error("Fill in all Twilio settings above and save first.")
            elif not test_to:
                st.error("Enter a WhatsApp number above.")
            else:
                try:
                    from twilio.rest import Client
                    client  = Client(twilio_sid, twilio_token)
                    from_wa = twilio_from if twilio_from.startswith("whatsapp:") else f"whatsapp:{twilio_from}"
                    to_wa   = test_to if test_to.startswith("whatsapp:") else f"whatsapp:{test_to}"
                    client.messages.create(
                        body="✓ SME Co-Pilot test message — WhatsApp is working!",
                        from_=from_wa, to=to_wa,
                    )
                    st.success(f"✓ WhatsApp sent to {test_to}")
                except ImportError:
                    st.error("Twilio not installed. Run: pip install twilio")
                except Exception as e:
                    st.error(f"WhatsApp failed: {e}")
