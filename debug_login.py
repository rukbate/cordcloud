import requests
import urllib3
import re

urllib3.disable_warnings()

host = 'cordcloud.us'
login_url = f'https://{host}/auth/login'

session = requests.session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
})

print(f"Fetching {login_url}...")
response = session.get(login_url, timeout=10, verify=False)

print(f"Status Code: {response.status_code}")
print(f"Encoding: {response.encoding}")
print("\n=== Response Headers ===")
for key, value in response.headers.items():
    print(f"{key}: {value}")

print("\n=== Response Body (first 3000 chars) ===")
print(response.text[:3000])

print("\n=== Looking for tokens and form fields ===")
# Look for all input fields
inputs = re.findall(r'<input[^>]*>', response.text)
for inp in inputs:
    print(f"Found: {inp}")

# Look for hidden values
tokens = re.findall(r'(csrf|token|_token)["\']?\s*[:\=]\s*["\']([^"\']+)["\']', response.text, re.IGNORECASE)
print("\nTokens found:")
for token_type, token_value in tokens:
    print(f"  {token_type}: {token_value}")

# Look for meta tags
metas = re.findall(r'<meta[^>]*>', response.text)
print("\nMeta tags:")
for meta in metas:
    print(f"  {meta}")

# Save full response to file for inspection
with open('/Users/lin/shadows/cordcloud/login_page.html', 'w', encoding='utf-8') as f:
    f.write(response.text)
print("\n✓ Full response saved to login_page.html")
