import json
from urllib.parse import urlparse
import os

def analyze_har(file_path):
    print(f"Analyzing {file_path}...")
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            har_data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file {file_path}")
        return

    entries = har_data.get('log', {}).get('entries', [])
    print(f"Total entries: {len(entries)}")

    unique_urls = set()
    relevant_data = []

    for entry in entries:
        request = entry.get('request', {})
        url = request.get('url', '')
        method = request.get('method', '')
        
        parsed_url = urlparse(url)
        # Focus on API calls
        if 'api' in parsed_url.path or 'graph' in parsed_url.netloc or 'json' in parsed_url.path:
             unique_urls.add(f"{method} {url}")

        response = entry.get('response', {})
        content = response.get('content', {})
        text = content.get('text', '')
        
        # Basic keyword search in response
        if text:
            lower_text = text.lower()
            # Look for fee related terms
            keywords = ['fee', 'apr', 'reward', 'emissions']
            if any(kw in lower_text for kw in keywords):
                 relevant_data.append({
                     'url': url,
                     'matches': [kw for kw in keywords if kw in lower_text],
                     'preview': text[:500] # Preview start of response
                 })

    print("\n--- Unique API URLs ---")
    for u in sorted(unique_urls):
        print(u)

    print("\n--- Responses with Keywords (First 5) ---")
    for item in relevant_data[:5]:
        print(f"URL: {item['url']}")
        print(f"Matches: {item['matches']}")
        print(f"Preview: {item['preview']}...")
        print("-" * 20)

if __name__ == "__main__":
    analyze_har('/home/adrd/skrypty/temp/base_aero_rewards/aerodrome.finance.har')
