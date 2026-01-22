from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import csv
import time
import re
from datetime import datetime
import random

class DarazScraper:
    def __init__(self):
        self.base_url = "https://www.daraz.com.np"
        
        # ✅ DARAZ SELECTORS (Based on provided HTML) - DO NOT CHANGE
        self.selectors = {
            # Product containers
            'product_container': [
                'div.Bm3ON[data-qa-locator="product-item"]',
                'div[data-qa-locator="product-item"]',
                'div.Bm3ON'
            ],
            
            # Title 
            'title': [
                'div.RfADt a',
                'a[title]'
            ],
            
            # Price 
            'price': [
                'div.aBrP0 span.ooOxS',
                'span.ooOxS'
            ],
            
            # Number sold 
            'sold_count': [
                'span._1cEkb span',
                'span._1cEkb'
            ],
            
            # Rating stars 
            'rating_container': [
                'div.mdmmT._32vUv',
                'div.mdmmT'
            ],
            
            # Review count 
            'review_count': [
                'span.qzqFw'
            ],
            
            # Province/Location -
            'province': [
                'span.oa6ri'
            ],
            
            # Product URL - <a> tag with href
            'product_link': [
                'div.RfADt a[href]',
                'a[href*=".html"]'
            ]
        }
    
    def extract_top_products(self, html, search_term, max_products=40):
        """Extract top N products in order from Daraz search results"""
        soup = BeautifulSoup(html, 'html.parser')
        products = []
        
        # Find ALL product containers
        all_containers = []
        
        for selector in self.selectors['product_container']:
            containers = soup.select(selector)
            if containers:
                print(f"   Found {len(containers)} products with selector: {selector}")
                all_containers.extend(containers)
                break  # Use the first selector that works
        
        # Remove duplicates while preserving order
        seen = set()
        unique_containers = []
        for container in all_containers:
            container_id = container.get('data-item-id', '')
            if container_id and container_id not in seen:
                seen.add(container_id)
                unique_containers.append(container)
        
        print(f"   Unique product containers: {len(unique_containers)}")
        
        # Extract top N products
        for i, container in enumerate(unique_containers[:max_products]):
            try:
                product_data = self.extract_single_product(container)
                if product_data:
                    product_data['search_rank'] = i + 1
                    product_data['search_term'] = search_term
                    products.append(product_data)
                    
                    print(f"   #{i+1}: {product_data['title'][:60]}...")
                    print(f"      Price: {product_data['price']} | Rating: {product_data['rating']} | Sold: {product_data['sold_count']}")
            except Exception as e:
                print(f"   ⚠️ Error on product {i+1}: {e}")
                continue
        
        return products
    
    def extract_single_product(self, container):
        """Extract data from a single product container"""
        data = {}
        
        # 1. ITEM ID (Daraz's product identifier)
        data['item_id'] = container.get('data-item-id', '')
        
        # 2. TITLE
        title = None
        title_elem = container.select_one('div.RfADt a')
        
        if title_elem:
            # Try to get from title attribute first (most complete)
            title = title_elem.get('title', '').strip()
            
            # If no title attribute, get text content
            if not title:
                title = title_elem.get_text(strip=True)
        
        if not title or len(title) < 5:
            return None
        
        data['title'] = title
        
        # 3. PRICE
        price = "N/A"
        price_elem = container.select_one('div.aBrP0 span.ooOxS')
        
        if price_elem:
            price = price_elem.get_text(strip=True)
            # Clean up price: "Rs. 59,990" -> "Rs. 59,990"
            price = price.strip()
        
        data['price'] = price
        
        # 4. NUMBER SOLD
        sold_count = "0"
        sold_elem = container.select_one('span._1cEkb span')
        
        if sold_elem:
            sold_text = sold_elem.get_text(strip=True)
            # Extract number from "55 sold" or "128 sold"
            sold_match = re.search(r'(\d+)\s*sold', sold_text, re.IGNORECASE)
            if sold_match:
                sold_count = sold_match.group(1)
        
        data['sold_count'] = sold_count
        
        # 5. RATING (count filled stars)
        rating = "N/A"
        rating_container = container.select_one('div.mdmmT._32vUv') or container.select_one('div.mdmmT')
        
        if rating_container:
            # Count filled stars (class contains 'Dy1nx') vs half/empty stars
            filled_stars = len(rating_container.select('i._9-ogB.Dy1nx'))
            half_stars = len(rating_container.select('i._9-ogB.JhD\\+v')) 
            
            # Calculate rating
            rating_value = filled_stars + (0.5 if half_stars > 0 else 0)
            rating = str(rating_value) if rating_value > 0 else "N/A"
        
        data['rating'] = rating
        
        # 6. REVIEW COUNT (number in parentheses)
        review_count = "0"
        review_elem = container.select_one('span.qzqFw')
        
        if review_elem:
            review_text = review_elem.get_text(strip=True)
            # Extract number from "(18)" or "(35)"
            review_match = re.search(r'\((\d+)\)', review_text)
            if review_match:
                review_count = review_match.group(1)
        
        data['review_count'] = review_count
        
        # 7. PROVINCE/LOCATION
        province = "N/A"
        province_elem = container.select_one('span.oa6ri')
        
        if province_elem:
            # Try title attribute first, then text content
            province = province_elem.get('title', '').strip()
            if not province:
                province = province_elem.get_text(strip=True)
        
        data['province'] = province
        
        # 8. PRODUCT URL
        product_url = ""
        link_elem = container.select_one('div.RfADt a[href]')
        
        if link_elem and link_elem.get('href'):
            href = link_elem['href']
            
            # Handle relative URLs
            if href.startswith('//'):
                product_url = 'https:' + href
            elif href.startswith('/'):
                product_url = self.base_url + href
            elif href.startswith('http'):
                product_url = href
            else:
                product_url = self.base_url + '/' + href
        
        data['product_url'] = product_url
        
        # 9. TIMESTAMP
        data['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return data
    
    def filter_products(self, products, min_sold=1, min_rating=1.0):
        """
        Filter products based on sold count and rating
        
        Args:
            products: List of product dictionaries
            min_sold: Minimum number of items sold (default: >1 means >= 2)
            min_rating: Minimum rating value (default: >1 means >= 1.5)
        
        Returns:
            Filtered list of products
        """
        filtered = []
        
        for product in products:
            try:
                # Get sold count
                sold_count = int(product.get('sold_count', '0'))
                
                # Get rating
                rating_str = product.get('rating', 'N/A')
                if rating_str == 'N/A':
                    rating = 0
                else:
                    rating = float(rating_str)
                
                # Filter: sold_count > 1 AND rating > 1
                if sold_count > min_sold and rating > min_rating:
                    filtered.append(product)
                    
            except (ValueError, TypeError):
                # Skip products with invalid data
                continue
        
        return filtered
    
    def scrape_with_stealth(self, search_query, max_products=40, fast_mode=True):
        """Scrape Daraz with stealth settings"""
        print(f"\n🎯 DARAZ SCRAPE: {search_query}")
        print("="*60)
        
        # Daraz Nepal search URL
        encoded_query = search_query.replace(' ', '+')
        search_url = f"https://www.daraz.com.np/catalog/?q={encoded_query}"
        
        all_products = []
        
        try:
            with sync_playwright() as p:
                # Launch with stealth settings
                launch_args = [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                ]
                
                browser = p.chromium.launch(
                    headless=False, 
                    args=launch_args
                )
                
                # Create context with realistic settings
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='Asia/Kathmandu', 
                    color_scheme='light',
                )
                
                page = context.new_page()
                
                # Add stealth scripts
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                """)
                
                # Navigate to search results
                print(f"   Loading: {search_query}")
                
                if fast_mode:
                    # Go directly to search results
                    print("   🚀 Fast mode: Going directly to search results...")
                    page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
                    time.sleep(random.uniform(3, 5))
                else:
                    # Human-like: Homepage first, then search
                    page.goto("https://www.daraz.com.np", wait_until='domcontentloaded', timeout=60000)
                    time.sleep(random.uniform(2, 4))
                    
                    # Type in search box
                    search_box = page.locator('input[type="search"]').first
                    search_box.click()
                    time.sleep(0.5)
                    search_box.fill(search_query)
                    time.sleep(1)
                    page.keyboard.press('Enter')
                    
                    # Wait for results
                    time.sleep(random.uniform(5, 8))
                
                # Scroll to load all products (important for getting all 40)
                print("   Scrolling to load all content...")
                for i in range(5):  # Increased scrolls to load all 40 products
                    scroll_amount = random.randint(500, 1000)
                    page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                    time.sleep(random.uniform(1, 2))
                
                # Scroll to bottom to ensure everything is loaded
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                
                # Get page content
                html = page.content()
                
                # Save HTML for debugging
                debug_filename = f"debug_daraz_{search_query.replace(' ', '_')}.html"
                with open(debug_filename, 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"   Saved HTML to {debug_filename}")
                
                # Extract products
                products = self.extract_top_products(html, search_query, max_products)
                all_products.extend(products)
                
                print(f"\n   ✅ Successfully extracted {len(products)} products")
                
                # Close browser
                browser.close()
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        return all_products
    
    def save_results(self, products, filename=None, include_filtered=True):
        """Save results to CSV"""
        if not products:
            print("⚠️ No products to save")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"daraz_products_{timestamp}.csv"
        
        # Sort by search rank
        products.sort(key=lambda x: x.get('search_rank', 99))
        
        # Save ALL products
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'search_rank', 'search_term', 'title', 'price', 'rating',
                'review_count', 'sold_count', 'province', 'item_id',
                'product_url', 'scraped_at'
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for product in products:
                writer.writerow(product)
        
        print(f"\n💾 Saved {len(products)} products to '{filename}'")
        
        # Create and save FILTERED version (sold > 1 AND rating > 1)
        if include_filtered:
            filtered_products = self.filter_products(products, min_sold=1, min_rating=1.0)
            
            if filtered_products:
                filtered_filename = filename.replace('.csv', '_filtered.csv')
                
                with open(filtered_filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for product in filtered_products:
                        writer.writerow(product)
                
                print(f"💾 Saved {len(filtered_products)} filtered products to '{filtered_filename}'")
                print(f"   (Products with sold > 1 AND rating > 1)")
        
        # Print summary
        print(f"\n{'='*60}")
        print("📊 ALL PRODUCTS SUMMARY")
        print(f"{'='*60}")
        
        for product in products[:10]:  # Show first 10
            rank = product['search_rank']
            print(f"\n#{rank} {product['title'][:70]}...")
            print(f"   Price: {product['price']} | ⭐ {product['rating']}/5 ({product['review_count']} reviews)")
            print(f"   Sold: {product['sold_count']} | Location: {product['province']}")
        
        if len(products) > 10:
            print(f"\n... and {len(products) - 10} more products")
        
        # Print filtered summary
        if include_filtered and filtered_products:
            print(f"\n{'='*60}")
            print("📊 FILTERED PRODUCTS SUMMARY (Sold > 1 AND Rating > 1)")
            print(f"{'='*60}")
            
            for product in filtered_products[:10]:
                rank = product['search_rank']
                print(f"\n#{rank} {product['title'][:70]}...")
                print(f"   Price: {product['price']} | ⭐ {product['rating']}/5 ({product['review_count']} reviews)")
                print(f"   Sold: {product['sold_count']} | Location: {product['province']}")
            
            if len(filtered_products) > 10:
                print(f"\n... and {len(filtered_products) - 10} more filtered products")
        
        return filename
    
    def run_scrape(self, search_terms=None, max_products=40):
        """Main execution"""
        print("🚀 DARAZ SCRAPER 2026")
        print("="*60)
        print("Features:")
        print("✅ Daraz Nepal selectors")
        print("✅ Product link, title, price, sold count, rating, province")
        print(f"✅ Max products per search: {max_products} (full page)")
        print("✅ Auto-filtering for: sold > 1 AND rating > 1")
        print("="*60)
        
        # Default search terms if none provided
        if not search_terms:
            search_terms = [
                "samsung smart tv",
                "lg smart tv",
                "himstar smart tv"
            ]
        
        all_products = []
        
        for i, search in enumerate(search_terms):
            print(f"\n{'#'*60}")
            print(f"SEARCHING: '{search}' ({i+1}/{len(search_terms)})")
            print(f"{'#'*60}")
            
            products = self.scrape_with_stealth(
                search, 
                max_products=max_products,
                fast_mode=True
            )
            all_products.extend(products)
            
            print(f"Total products collected: {len(all_products)}")
            
            # Wait between searches
            if search != search_terms[-1]:
                wait_time = random.uniform(10, 20)
                print(f"\n⏸️ Waiting {wait_time:.1f}s before next search...")
                time.sleep(wait_time)
        
        # Save results
        if all_products:
            filename = self.save_results(all_products, include_filtered=True)
            
            print(f"\n{'='*60}")
            print("✅ SCRAPING COMPLETE!")
            print(f"{'='*60}")
            print(f"📊 Total products scraped: {len(all_products)}")
            
            # Calculate filtered count
            filtered = self.filter_products(all_products, min_sold=1, min_rating=1.0)
            print(f"📊 Filtered products (sold > 1 & rating > 1): {len(filtered)}")
            
            print(f"\n💾 Files created:")
            print(f"   - {filename} (all products)")
            print(f"   - {filename.replace('.csv', '_filtered.csv')} (filtered)")
            
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
    
    # Run the scraper
    scraper = DarazScraper()
    
    try:
        print("\n⚠️ IMPORTANT: Browser will open (visible).")
        print("   Watch for any issues or CAPTCHAs.")
        
        # Customize your search terms here
        custom_searches = [
            "samsung smart tv",
            "lg smart tv", 
            "himstar smart tv"
        ]
        
        print(f"\n📋 Will search for: {', '.join(custom_searches)}")
        print(f"   Products per search: 40 (full page)")
        print(f"   Filtering: sold > 1 AND rating > 1")
        
        confirm = input("\nPress ENTER to start (or Ctrl+C to cancel)...")
        
        results_file = scraper.run_scrape(
            search_terms=custom_searches,
            max_products=40  # Changed from 10 to 40
        )
        
        if results_file:
            print(f"\n🎉 Open the CSV files in Excel/Google Sheets")
            print("   Columns: Rank, Title, Price, Rating, Reviews, Sold, Province, URL")
            print(f"\n💡 TIP: Use the '_filtered.csv' file for products with:")
            print("   - More than 1 item sold")
            print("   - Rating higher than 1.0")
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()