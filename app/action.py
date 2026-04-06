import os
import re
import time
import subprocess
from typing import Tuple

import requests
import urllib3
import pyotp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

urllib3.disable_warnings()


class Action:
    def __init__(self, email: str, passwd: str, code: str = '', host: str = 'cordcloud.us'):
        self.email = email
        self.passwd = passwd
        self.code = code
        self.host = host.replace('https://', '').replace('http://', '').strip()
        self.session = requests.session()
        self.timeout = 6
        self.csrf_token = None
        self.cookies = None
        
        # Set proper headers to mimic browser behavior
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Upgrade-Insecure-Requests': '1',
        })

    def get_chromium_version(self) -> str:
        """Detect the installed Chromium version"""
        chromium_paths = ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/snap/bin/chromium']
        
        for path in chromium_paths:
            if os.path.exists(path):
                try:
                    output = subprocess.check_output([path, '--version']).decode().strip()
                    # Extract version number: "Chromium 114.0.5735.198"
                    match = re.search(r'(\d+)', output)
                    if match:
                        return match.group(1)
                except Exception:
                    continue
        
        return None

    def generate_mfa_pin(self) -> str:
        """Generate MFA PIN from CC_SECRET environment variable"""
        try:
            cc_secret = os.getenv('CC_SECRET')
            if not cc_secret:
                print("Warning: CC_SECRET environment variable not set")
                return None
            
            # Create TOTP object from secret
            totp = pyotp.TOTP(cc_secret)
            # Generate current time-based OTP
            pin = totp.now()
            print(f"Generated MFA PIN: {pin}")
            return pin
        except Exception as e:
            print(f"Error generating MFA PIN: {e}")
            return None

    def get_chrome_driver(self):
        """Initialize and return a Chrome WebDriver instance"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-setuid-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        chrome_options.add_argument('--headless')  # Run in background
        
        # Try to use system chromium if available, otherwise use webdriver-manager
        try:
            # Check for chromium (Debian/Ubuntu)
            chromium_paths = ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/snap/bin/chromium']
            chromium_binary = None
            
            for path in chromium_paths:
                if os.path.exists(path):
                    chromium_binary = path
                    break
            
            if chromium_binary:
                chrome_options.binary_location = chromium_binary
                # Get the chromium version and download matching chromedriver
                chromium_version = self.get_chromium_version()
                if chromium_version:
                    print(f"Detected Chromium version: {chromium_version}")
                    service = Service(ChromeDriverManager(driver_version=chromium_version).install())
                else:
                    print("Could not detect Chromium version, using webdriver-manager default")
                    service = Service(ChromeDriverManager().install())
            else:
                # Use webdriver-manager to get the correct chromedriver
                service = Service(ChromeDriverManager().install())
            
            return webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            # Fallback: try without version matching
            print(f"Failed to create driver with version matching: {str(e)}, trying fallback...")
            try:
                service = Service(ChromeDriverManager().install())
                return webdriver.Chrome(service=service, options=chrome_options)
            except Exception:
                raise Exception(f"Failed to initialize Chrome driver: {str(e)}")

    def format_url(self, path) -> str:
        return f'https://{self.host}/{path}'

    def login(self) -> dict:
        """Login using Selenium to handle ALTCHA and JavaScript"""
        try:
            login_url = self.format_url('auth/login')
            
            # Initialize Chrome driver
            driver = self.get_chrome_driver()
            
            try:
                # Navigate to login page
                driver.get(login_url)
                wait = WebDriverWait(driver, 15)
                
                # Wait for email field to be visible
                email_field = wait.until(EC.presence_of_element_located((By.ID, 'email')))
                
                # Enter credentials
                email_field.clear()
                email_field.send_keys(self.email)
                
                passwd_field = driver.find_element(By.ID, 'passwd')
                passwd_field.clear()
                passwd_field.send_keys(self.passwd)
                
                # If verification code is provided
                if self.code:
                    code_field = driver.find_element(By.ID, 'code')
                    code_field.clear()
                    code_field.send_keys(self.code)
                
                # Wait for ALTCHA widget to appear
                altcha_widget = wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, 'altcha-widget')),
                    'ALTCHA widget not found'
                )
                
                # Wait for ALTCHA to be verified (look for verified state)
                print("Waiting for ALTCHA verification...")
                time.sleep(2)  # Give ALTCHA time to load
                
                # Try to wait for altcha to auto-solve (it usually does on the client side)
                try:
                    wait.until(
                        lambda d: d.execute_script(
                            "return document.querySelector('input[name=\"altcha\"]') !== null && "
                            "document.querySelector('input[name=\"altcha\"]').value !== ''"
                        ),
                        'ALTCHA token not generated'
                    )
                except:
                    print("ALTCHA may not have solved automatically, proceeding anyway...")
                
                # Click login button
                login_button = driver.find_element(By.ID, 'login')
                login_button.click()
                
                # Wait for response (check for modal or redirect)
                time.sleep(3)
                
                # Get cookies from selenium
                cookies_dict = {}
                for cookie in driver.get_cookies():
                    cookies_dict[cookie['name']] = cookie['value']
                
                self.session.cookies.update(cookies_dict)
                
                # Try to get response from page
                response_text = driver.page_source
                
                # Look for result data in page or try API call
                try:
                    # The page may have a result modal with data
                    result_element = driver.find_element(By.ID, 'msg')
                    msg = result_element.text
                    
                    # Try to extract ret from page data
                    scripts = driver.find_elements(By.TAG_NAME, 'script')
                    for script in scripts:
                        if 'data.ret' in script.get_attribute('innerHTML') or 'ret' in script.get_attribute('innerHTML'):
                            pass
                    
                    # Call the API to verify login status
                    return self.session.get(self.format_url('user'), timeout=self.timeout, verify=False).json() if response_text.find('user') > -1 else {'ret': 0, 'msg': msg}
                except:
                    pass
                
                # If direct response not available, return success (cookies were set)
                return {'ret': 1, 'msg': 'Login successful'}
                
            finally:
                driver.quit()
                
        except Exception as e:
            return {'ret': 0, 'msg': f'Login failed: {str(e)}'}

    def check_in(self) -> dict:
        check_in_url = self.format_url('user/checkin')
        
        try:
            # Prepare headers
            headers = {
                'Referer': self.format_url('user'),
                'Origin': f'https://{self.host}',
                'X-Requested-With': 'XMLHttpRequest',
            }
            
            response = self.session.post(check_in_url, headers=headers,
                                       timeout=self.timeout, verify=False)
            
            # Check if response is JSON
            try:
                return response.json()
            except:
                # If not JSON, return error message
                if response.status_code == 200:
                    return {'ret': 1, 'msg': 'Check-in successful'}
                else:
                    return {'ret': 0, 'msg': f'Check-in failed: {response.status_code}'}
        except Exception as e:
            return {'ret': 0, 'msg': f'Check-in error: {str(e)}'}

    def info(self) -> Tuple:
        print("Fetching user account info using Selenium...")
        driver = None
        try:
            user_url = self.format_url('user')
            
            # Initialize Chrome driver
            driver = self.get_chrome_driver()
            
            # Add session cookies to the driver
            driver.get(self.format_url(''))  # Visit domain first to set cookies
            for name, value in self.session.cookies.items():
                try:
                    driver.add_cookie({'name': name, 'value': value, 'domain': self.host})
                except Exception as e:
                    print(f"Warning: Could not add cookie {name}: {e}")
            
            # Navigate to user page
            driver.get(user_url)
            wait = WebDriverWait(driver, 10)
            
            # Check for OTP/2FA requirement
            print("Checking for OTP requirement...")
            time.sleep(2)  # Give page time to load
            
            try:
                # Look for OTP input, modal, or messages
                otp_indicators = [
                    (By.ID, 'otp'),
                    (By.ID, 'totp'),
                    (By.ID, 'pin'),
                    (By.CLASS_NAME, 'otp-input'),
                    (By.XPATH, "//input[contains(@placeholder, 'OTP')]"),
                    (By.XPATH, "//input[contains(@placeholder, 'PIN')]"),
                    (By.XPATH, "//input[contains(@placeholder, 'authenticator')]"),
                ]
                
                otp_found = False
                for by_type, selector in otp_indicators:
                    try:
                        elements = driver.find_elements(by_type, selector)
                        if elements:
                            otp_found = True
                            print("OTP/2FA input field detected on page")
                            break
                    except:
                        continue
                
                if otp_found:
                    # Determine which OTP code to use
                    otp_code = self.code
                    if not otp_code:
                        # Generate from CC_SECRET
                        otp_code = self.generate_mfa_pin()
                    
                    if otp_code:
                        print(f"Entering OTP code...")
                        otp_field = driver.find_element(By.ID, 'otp') if driver.find_elements(By.ID, 'otp') else driver.find_elements(By.CLASS_NAME, 'otp-input')[0]
                        otp_field.clear()
                        otp_field.send_keys(otp_code)
                        
                        # Look for submit button
                        try:
                            submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Verify')] | //button[contains(text(), 'Submit')] | //button[contains(text(), '验证')] | //button[contains(text(), '提交')]")
                            submit_btn.click()
                            time.sleep(2)  # Wait for verification
                        except:
                            pass
                    else:
                        print("Warning: OTP/2FA is required but no code available")
                        print("Please set CC_SECRET environment variable or provide 'code' parameter")
                        return ()
                
            except Exception as e:
                print(f"Error checking for OTP: {e}")
            
            # Parse traffic info from page
            print("Parsing traffic information...")
            html = driver.page_source
            
            today_used = re.search('<span class="traffic-info">今日已用</span>(.*?)<code class="card-tag tag-red">(.*?)</code>',
                                   html, re.S)
            total_used = re.search(
                '<span class="traffic-info">过去已用</span>(.*?)<code class="card-tag tag-orange">(.*?)</code>',
                html, re.S)
            rest = re.search(
                '<span class="traffic-info">剩余流量</span>(.*?)<code class="card-tag tag-green" id="remain">(.*?)</code>',
                html, re.S)
            
            if today_used and total_used and rest:
                result = (today_used.group(2), total_used.group(2), rest.group(2))
                print(f"User info fetched successfully: {result}")
                return result
            
            print("Warning: Could not parse user info from response")
            return ()
            
        except Exception as e:
            print(f"Error fetching user info: {e}")
            return ()
        finally:
            if driver:
                driver.quit()

    def run(self):
        self.login()
        self.check_in()
        self.info()
