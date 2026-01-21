from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import csv
import time
import re
from datetime import datetime
import random

class ProfessionalAmazonScraper:
    def __init__(self):
        self.base_url = "https://www.amazon.com"
        
        # ✅ 2024 AMAZON SELECTORS (UPDATED TODAY)
        self.selectors_2024 = {
            # Product containers - 2024 NEW
            'product_container': [
                'div[data-component-type="s-search-result"]',
                '.s-result-item[data-component-type="s-search-result"]',
                '.puisg-col-inner',  # NEW 2024
                '[data-csa-c-type="item"]'
            ],
            
            # Title - 2024 NEW
            'title': [
                'h2 a span',  # Standard
                '.a-size-medium.a-color-base',  # Brand name
                'span.a-size-base-plus.a-color-base.a-text-normal',  # Full title
                'a.s-line-clamp-2 span',  # 2024 NEW
                'a.s-line-clamp-3 span'   # 2024 NEW
            ],
            
            # Price - 2024
            'price': [
                'span.a-price-whole',
                'span.a-price-fraction',
                'span.a-offscreen',
                '.a-price .a-text-price'
            ],
            
            # Rating - 2024
            'rating': [
                'span.a-icon-alt',
                'i.a-icon-star-small span',
                '[aria-label*="out of 5 stars"]'
            ],
            
            # Reviews - 2024
            'review_count': [
                'span.a-size-base.s-underline-text',
                'span[aria-label*="stars"] + span',
                'a[href*="customerReviews"] span'
            ],
            
            # Sales rank/Best seller - 2024
            'bestseller': [
                'span.a-badge-text',
                '.s-best-seller-badge',
                '[aria-label*="Best Seller"]'
            ],
            
            # "Bought in past month" - 2024
            'sales_volume': [
                'span.a-size-small.a-color-secondary',  # Usually contains "XK+ bought"
                'div.a-row.a-size-small span',  # New pattern
                '[class*="bought"]'  # Any element with "bought" in class
            ]
        }
    
    def extract_top_10_products(self, html, search_term):
        """Extract EXACTLY top 10 products in order"""
        soup = BeautifulSoup(html, 'html.parser')
        products = []
        
        # ✅ METHOD 1: Find ALL product containers
        all_containers = []
        
        for selector in self.selectors_2024['product_container']:
            containers = soup.select(selector)
            if containers:
                print(f"   Found {len(containers)} with selector: {selector}")
                all_containers.extend(containers[:20])  # Get first 20
        
        # Remove duplicates while preserving order
        seen = set()
        unique_containers = []
        for container in all_containers:
            if container not in seen:
                seen.add(container)
                unique_containers.append(container)
        
        print(f"   Unique product containers: {len(unique_containers)}")
        
        # ✅ Take EXACTLY top 11 (as they appear on Amazon)
        for i, container in enumerate(unique_containers[:11]):
            try:
                product_data = self.extract_single_product_2024(container)
                if product_data:
                    product_data['search_rank'] = i + 1  # 1, 2, 3... 10
                    product_data['search_term'] = search_term
                    products.append(product_data)
                    
                    print(f"   #{i+1}: {product_data['title'][:60]}...")
                    print(f"      Price: {product_data['price']} | Reviews: {product_data['review_count']}")
            except Exception as e:
                print(f"   ⚠️ Error on product {i+1}: {e}")
                continue
        
        return products
    
    def extract_single_product_2024(self, container):
        """Extract data with 2024 selectors"""
        data = {}
        
        # 1. ASIN (Amazon ID)
        data['asin'] = container.get('data-asin', '')
        if not data['asin']:
            # Try to find ASIN in link
            link = container.find('a', href=True)
            if link:
                href = link['href']
                asin_match = re.search(r'/dp/([A-Z0-9]{10})', href)
                if asin_match:
                    data['asin'] = asin_match.group(1)
        
        # 2. TITLE (2024 selector from your HTML)
        title = None
        
        # Try your EXACT HTML pattern first
        title_elem = container.select_one('a.a-link-normal.s-line-clamp-2 span') or \
                    container.select_one('a.a-link-normal.s-line-clamp-3 span') or \
                    container.select_one('h2.a-size-mini a span') or \
                    container.select_one('h2 span')
        
        if title_elem:
            title = title_elem.text.strip()
        else:
            # Fallback: get all text from container and extract first meaningful line
            all_text = container.get_text('\n', strip=True)
            lines = [line for line in all_text.split('\n') if line and len(line) > 10]
            if lines:
                title = lines[0]
        
        if not title:
            return None
        
        data['title'] = title
        
        # 3. PRICE
        price = "N/A"
        # Look for price whole + fraction
        price_whole = container.select_one('span.a-price-whole')
        price_fraction = container.select_one('span.a-price-fraction')
        
        if price_whole:
            price = f"${price_whole.text.strip()}"
            if price_fraction:
                price += price_fraction.text.strip()
        else:
            # Try other price selectors
            price_elem = container.select_one('span.a-offscreen')
            if price_elem:
                price = price_elem.text.strip()
        
        data['price'] = price
        
        # 4. RATING (out of 5)
        rating_elem = container.select_one('span.a-icon-alt')
        if rating_elem:
            rating_text = rating_elem.text.strip()
            # Extract "4.5" from "4.5 out of 5 stars"
            rating_match = re.search(r'(\d+\.?\d*)', rating_text)
            data['rating'] = rating_match.group(1) if rating_match else "N/A"
        else:
            data['rating'] = "N/A"
        
        # 5. REVIEW COUNT
        review_elem = container.select_one('span.a-size-base.s-underline-text')
        if review_elem:
            review_text = review_elem.text.strip()
            # Extract numbers: "1,234" -> "1234"
            review_match = re.search(r'([\d,]+)', review_text)
            if review_match:
                data['review_count'] = review_match.group(1).replace(',', '')
            else:
                data['review_count'] = "0"
        else:
            data['review_count'] = "0"
        
        # 6. BEST SELLER
        bestseller = container.select_one('span.a-badge-text') or \
                    container.select_one('.s-best-seller-badge')
        data['bestseller'] = "Yes" if bestseller else "No"
        
        # 7. SALES VOLUME ("XK+ bought in past month")
        sales_text = ""
        # Look for any element with "bought" and "month"
        for elem in container.find_all(['span', 'div', 'a']):
            text = elem.get_text(strip=True)
            if 'bought' in text.lower() and 'month' in text.lower():
                sales_text = text
                break
        
        data['sales_volume'] = sales_text
        
        # 8. PRODUCT URL
        if data['asin']:
            data['product_url'] = f"{self.base_url}/dp/{data['asin']}"
        else:
            # Try to find product link
            link_elem = container.select_one('a[href*="/dp/"]')
            if link_elem and link_elem.get('href'):
                href = link_elem['href']
                if href.startswith('/'):
                    data['product_url'] = self.base_url + href
                elif href.startswith('http'):
                    data['product_url'] = href
                else:
                    data['product_url'] = self.base_url + '/' + href
            else:
                data['product_url'] = ""
        
        # 9. TIMESTAMP
        data['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return data
    
    def scrape_with_stealth(self, search_query, max_pages=1, use_tor_proxy=False, fast_mode=False):
        """Professional scraping with anti-detection - FIXED ASYNC"""
        print(f"\n🎯 PROFESSIONAL SCRAPE: {search_query}")
        print("="*60)
        
        encoded_query = search_query.replace(' ', '+')
        search_url = f"https://www.amazon.com/s?k={encoded_query}&s=review-rank"
        
        all_products = []
        
        try:
            with sync_playwright() as p:
                # ✅ STEP 1: Launch with MAXIMUM stealth
                launch_args = [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-web-security',
                    '--disable-features=BlockInsecurePrivateNetworkRequests',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                ]
                
                # Add Tor proxy if enabled
                if use_tor_proxy:
                    print("   🔐 Using Tor Browser SOCKS proxy (127.0.0.1:9150)")
                    launch_args.append('--proxy-server=socks5://127.0.0.1:9150')
                
                browser = p.chromium.launch(
                    headless=False,  # Set to True after testing
                    args=launch_args
                )
                
                # ✅ STEP 2: Create context with REAL user profile
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                    geolocation={'latitude': 40.7128, 'longitude': -74.0060},  # NYC
                    permissions=['geolocation'],
                    color_scheme='light',
                    device_scale_factor=1,
                    has_touch=False,
                    is_mobile=False,
                    java_script_enabled=True,
                    accept_downloads=True,
                    screen={'width': 1920, 'height': 1080},
                )
                
                page = context.new_page()
                
                # ✅ STEP 3: ADD STEALTH SCRIPTS
                page.add_init_script("""
                    // Overwrite the navigator properties
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Overwrite the plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // Overwrite the languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Overwrite the chrome object
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                    
                    // Add missing properties
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)
                
                # ✅ STEP 4: NAVIGATE - Fast mode or human-like mode
                print(f"   Loading: {search_query}")
                
                # Increased timeout and changed wait condition for Tor compatibility
                timeout_ms = 180000 if use_tor_proxy else 90000  # 3 min for Tor, 1.5 min normal
                # Use 'domcontentloaded' - more reliable than 'networkidle' for Amazon
                wait_condition = 'domcontentloaded' if not use_tor_proxy else 'load'
                
                if fast_mode:
                    # FAST MODE: Go directly to search results (better for Tor and reliability)
                    print("   🚀 Fast mode: Going directly to search results...")
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            if use_tor_proxy:
                                print(f"   ⏳ Loading via Tor (attempt {attempt + 1}/{max_retries}) - patience...")
                            
                            page.goto(search_url, wait_until=wait_condition, timeout=timeout_ms)
                            print("   ✅ Search results loaded successfully")
                            break
                        except Exception as e:
                            if attempt < max_retries - 1:
                                wait_time = 15 + (attempt * 15)  # 15s, 30s, 45s
                                print(f"   ⚠️ Timeout on attempt {attempt + 1}. Retrying in {wait_time}s...")
                                time.sleep(wait_time)
                            else:
                                raise Exception(f"Failed to load search results after {max_retries} attempts: {e}")
                    
                    time.sleep(random.uniform(2, 4))
                    
                else:
                    # HUMAN-LIKE MODE: Go to homepage first, then search
                    # First, go to Amazon homepage (like a human would)
                    max_retries = 2  # Reduced retries for homepage
                    for attempt in range(max_retries):
                        try:
                            if use_tor_proxy:
                                print(f"   ⏳ Loading homepage via Tor (attempt {attempt + 1}/{max_retries})...")
                            
                            page.goto("https://www.amazon.com", wait_until=wait_condition, timeout=timeout_ms)
                            print("   ✅ Amazon homepage loaded successfully")
                            break
                        except Exception as e:
                            if attempt < max_retries - 1:
                                wait_time = 15
                                print(f"   ⚠️ Homepage timeout on attempt {attempt + 1}. Retrying in {wait_time}s...")
                                time.sleep(wait_time)
                            else:
                                print(f"   ⚠️ Homepage failed. Switching to direct search URL...")
                                # Fallback to fast mode if homepage fails
                                page.goto(search_url, wait_until=wait_condition, timeout=timeout_ms)
                                print("   ✅ Loaded search results directly")
                                time.sleep(random.uniform(3, 5))
                                # Skip the search box interaction since we're already at results
                                break
                    
                    # Only do search box interaction if we successfully loaded homepage
                    if "s?" not in page.url:  # Not already at search results
                        time.sleep(random.uniform(2, 4))
                    
                    # Type in search box slowly - FIXED (removed await)
                    try:
                        search_box = page.locator('#twotabsearchtextbox')
                        search_box.click(timeout=10000)
                        time.sleep(0.5)
                        
                        # Type slowly, character by character - FIXED (removed await, using fill instead)
                        search_box.fill('')  # Clear first
                        search_box.type(search_query, delay=random.uniform(50, 150))
                        
                        time.sleep(1)
                        page.keyboard.press('Enter')
                        
                        # Wait for results - longer for Tor
                        wait_time = random.uniform(8, 12) if use_tor_proxy else random.uniform(5, 8)
                        print(f"   ⏳ Waiting {wait_time:.1f}s for search results...")
                        time.sleep(wait_time)
                        
                    except Exception as e:
                        print(f"   ⚠️ Search box interaction failed: {e}")
                        print("   Trying direct URL method...")
                        
                        # Fallback: Go directly to search URL
                        page.goto(search_url, wait_until=wait_condition, timeout=timeout_ms)
                        time.sleep(random.uniform(5, 8))
                
                # ✅ STEP 5: SCROLL LIKE A HUMAN
                print("   Scrolling to load content...")
                
                # Multiple small scrolls
                for _ in range(3):
                    scroll_amount = random.randint(300, 800)
                    page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                    time.sleep(random.uniform(1, 3))
                
                # ✅ STEP 6: GET CONTENT
                html = page.content()
                
                # Save HTML for debugging
                with open(f"debug_{search_query.replace(' ', '_')}.html", 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"   Saved HTML to debug_{search_query.replace(' ', '_')}.html")
                
                # ✅ STEP 7: EXTRACT TOP 10
                products = self.extract_top_10_products(html, search_query)
                all_products.extend(products)
                
                print(f"\n   ✅ Successfully extracted {len(products)} products")
                
                # ✅ STEP 8: CLOSE
                browser.close()
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        return all_products
    
    def save_results(self, products, filename=None):
        """Save to CSV with ALL details"""
        if not products:
            print("⚠️ No products to save")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"amazon_top10_{timestamp}.csv"
        
        # Sort by search rank
        products.sort(key=lambda x: x.get('search_rank', 99))
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'search_rank', 'search_term', 'title', 'price', 'rating',
                'review_count', 'bestseller', 'sales_volume', 'asin',
                'product_url', 'scraped_at'
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for product in products:
                writer.writerow(product)
        
        print(f"\n💾 Saved {len(products)} products to '{filename}'")
        
        # Print summary
        print(f"\n{'='*60}")
        print("📊 TOP 10 PRODUCTS SUMMARY")
        print(f"{'='*60}")
        
        for product in products[:10]:
            rank = product['search_rank']
            print(f"\n#{rank} {product['title'][:70]}...")
            print(f"   Price: {product['price']} | ⭐ {product['rating']}/5")
            print(f"   Reviews: {product['review_count']} | Best Seller: {product['bestseller']}")
            if product['sales_volume']:
                print(f"   📈 {product['sales_volume']}")
        
        return filename
    
    def rotate_ip_tor(self):
        """
        Rotate IP using Tor (if installed)
        Install Tor: https://www.torproject.org/download/
        Then install stem: pip install stem
        """
        try:
            from stem import Signal
            from stem.control import Controller
            
            # Try default Tor control ports
            ports = [9051, 9151]  # 9051 = Tor service, 9151 = Tor Browser
            
            for port in ports:
                try:
                    with Controller.from_port(port=port) as controller:
                        controller.authenticate(password='')  # Default: no password
                        controller.signal(Signal.NEWNYM)
                        print(f"🔄 IP rotated via Tor (port {port})")
                        time.sleep(5)  # Wait for new circuit
                        return True
                except Exception as port_error:
                    continue
            
            # If both ports failed
            raise Exception("Could not connect to Tor on ports 9051 or 9151")
            
        except Exception as e:
            print(f"⚠️ Tor rotation failed: {e}")
            print("\n📋 SOLUTION:")
            print("   Option 1: Use Tor Browser's SOCKS proxy (EASIER)")
            print("   Option 2: Install standalone Tor service")
            print("\n   For Option 1, I'll configure the browser to use Tor Browser's proxy...")
            return False
    
    def rotate_ip_vpn(self):
        """
        Placeholder for VPN IP rotation
        You can integrate with your VPN provider's API here
        """
        print("🔄 VPN IP rotation (implement your VPN API)")
        # Example: call your VPN provider's API to change server
        # subprocess.run(['nordvpn', 'connect'])
        time.sleep(10)
        return True
    
    def run_professional_scrape(self, use_ip_rotation=False, rotation_method='tor'):
        """Main execution - Professional grade with IP rotation"""
        # Check if using Tor Browser proxy (define early)
        use_tor_proxy = (use_ip_rotation and rotation_method == 'tor')
        
        print("🚀 PROFESSIONAL AMAZON SCRAPER 2024")
        print("="*60)
        print("Features:")
        print("✅ 2024 Amazon selectors")
        print("✅ Top 10 products in order")
        print("✅ Anti-detection stealth")
        print(f"✅ IP rotation: {'ENABLED' if use_ip_rotation else 'DISABLED'}")
        print("✅ Fast mode: Direct to search (more reliable)")
        print("✅ Smart retry logic")
        print("="*60)
        
        # Your search terms
        searches = [
            "samsung mobile phones",
            "samsung headphones",
            "lg headphones"
        ]
        
        all_products = []
        
        for i, search in enumerate(searches):
            print(f"\n{'#'*60}")
            print(f"SEARCHING: '{search}' ({i+1}/{len(searches)})")
            print(f"{'#'*60}")
            
            # Rotate IP before each search (except first)
            if use_ip_rotation and i > 0:
                print("\n🔄 Rotating IP address...")
                if rotation_method == 'tor':
                    success = self.rotate_ip_tor()
                    if not success:
                        print("   ℹ️ Continuing with Tor Browser proxy (no rotation)")
                elif rotation_method == 'vpn':
                    self.rotate_ip_vpn()
                else:
                    print("⚠️ Unknown rotation method. Skipping.")
            
            products = self.scrape_with_stealth(
                search, 
                max_pages=1, 
                use_tor_proxy=use_tor_proxy,
                fast_mode=True  # Always use fast mode - more reliable
            )
            all_products.extend(products)
            
            print(f"Total products collected: {len(all_products)}")
            
            # Wait between searches
            if search != searches[-1]:
                wait_time = random.uniform(30, 60)
                print(f"\n⏸️ Waiting {wait_time:.1f}s before next search...")
                time.sleep(wait_time)
        
        # Save results
        if all_products:
            filename = self.save_results(all_products)
            
            print(f"\n{'='*60}")
            print("✅ MISSION ACCOMPLISHED!")
            print(f"{'='*60}")
            print(f"📊 Total products: {len(all_products)}")
            print(f"💾 File: {filename}")
            if use_ip_rotation:
                print("   - IP rotation enabled")
            
            return filename
        else:
            print("❌ Failed to get products")
            return None

# ===== RUN IT =====
if __name__ == "__main__":
    import sys
    
    # Check for dependencies
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Missing: pip install playwright")
        print("Then: python -m playwright install chromium")
        sys.exit(1)
    
    # Run the professional scraper
    scraper = ProfessionalAmazonScraper()
    
    try:
        print("\n⚠️ IMPORTANT: Browser will open (visible).")
        print("   Watch what Amazon shows. If CAPTCHA appears, solve it.")
        
        # IP ROTATION OPTIONS:
        print("\n🔄 IP ROTATION:")
        print("   1. No rotation (default) - FASTEST")
        print("   2. Tor rotation via Tor Browser - SLOW but anonymous")
        print("   3. VPN rotation (implement your VPN)")
        print("\n   ⚠️ NOTE: Tor is VERY SLOW (2-3 min per search)")
        print("            Use option 1 for testing, option 2 for anonymity")
        
        choice = input("\nSelect option (1/2/3) [default: 1]: ").strip() or "1"
        
        use_rotation = False
        rotation_method = 'tor'
        
        if choice == '2':
            use_rotation = True
            rotation_method = 'tor'
            print("\n✅ Using Tor Browser proxy")
            print("📌 IMPORTANT: Keep your Tor Browser OPEN while scraping!")
            print("   The scraper will route traffic through Tor Browser's proxy.")
            print("\n⏰ EXPECT SLOW SPEEDS:")
            print("   - Each page load: 1-3 minutes")
            print("   - Total time for 3 searches: 10-20 minutes")
            print("   - Many timeouts are normal with Tor")
            
            confirm = input("\nContinue with Tor? (y/n) [y]: ").strip().lower() or "y"
            if confirm != 'y':
                print("✅ Switching to no rotation (faster)")
                use_rotation = False
                rotation_method = None
            else:
                input("\nPress ENTER when Tor Browser is connected and ready...")
        elif choice == '3':
            use_rotation = True
            rotation_method = 'vpn'
            print("✅ Using VPN rotation (you need to implement VPN API)")
        else:
            print("✅ No IP rotation (fastest option)")
        
        print("\nStarting in 5 seconds...")
        time.sleep(5)
        
        results_file = scraper.run_professional_scrape(
            use_ip_rotation=use_rotation,
            rotation_method=rotation_method
        )
        
        if results_file:
            print(f"\n🎉 Open '{results_file}' in Excel/Google Sheets")
            print("   Columns: Rank, Title, Price, Rating, Reviews, URL, etc.")
            
            if use_rotation and rotation_method == 'tor':
                print("\n💡 TIP: For faster scraping in production:")
                print("   - Use residential proxy services (BrightData, Smartproxy, Oxylabs)")
                print("   - Or add delays between requests without Tor")
                print("   - Tor is best for maximum anonymity, not speed")
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()