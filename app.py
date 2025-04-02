from flask import Flask, request, jsonify
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
import pandas as pd
import matplotlib.pyplot as plt
import os
import io
import base64
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv()

app = Flask(__name__)

def get_google_ads_client():
    # Check if we have a config file, otherwise use env vars
    if os.path.exists("google-ads.yaml"):
        return GoogleAdsClient.load_from_storage("google-ads.yaml")
    else:
        # Create configuration dictionary from environment variables
        credentials = {
            "developer_token": os.environ.get("DEVELOPER_TOKEN"),
            "client_id": os.environ.get("CLIENT_ID"),
            "client_secret": os.environ.get("CLIENT_SECRET"),
            "refresh_token": os.environ.get("REFRESH_TOKEN"),
            "login_customer_id": os.environ.get("LOGIN_CUSTOMER_ID"),
            "use_proto_plus": True
        }
        return GoogleAdsClient.load_from_dict(credentials)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "Google Ads API Service",
        "endpoints": {
            "/health": "Health check endpoint",
            "/api/keyword-ideas": "Get keyword ideas from Google Ads API"
        }
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/api/keyword-ideas', methods=['POST'])
def get_keyword_ideas():
    try:
        data = request.json
        customer_id = data.get('customer_id')
        keywords = data.get('keywords', [])
        
        # Get language and location parameters (changing parameter names for clarity)
        language = data.get('language', 'en')  # Accept simple codes like 'en'
        location = data.get('location', 'US')  # Accept simple codes like 'US'
        page_url = data.get('page_url')
        competitors_domains = data.get('competitors_domains', [])
        
        if not customer_id:
            return jsonify({"error": "Missing required parameter: customer_id"}), 400
            
        if not keywords and not page_url and not competitors_domains:
            return jsonify({"error": "You must provide at least one of: keywords, page_url, or competitors_domains"}), 400
        
        # Get client
        client = get_google_ads_client()
        
        # Get keyword ideas using the client
        keyword_ideas = generate_keyword_ideas(
            client,
            customer_id,
            keywords,
            language,
            location,
            page_url,
            competitors_domains
        )
        
        # Format the response
        formatted_results = []
        for idea in keyword_ideas:
            # Convert micros (millionths of a currency unit) to actual currency values
            low_top_of_page_bid = idea.keyword_idea_metrics.low_top_of_page_bid_micros / 1000000 if idea.keyword_idea_metrics.low_top_of_page_bid_micros else 0
            high_top_of_page_bid = idea.keyword_idea_metrics.high_top_of_page_bid_micros / 1000000 if idea.keyword_idea_metrics.high_top_of_page_bid_micros else 0
            
            formatted_results.append({
                "text": idea.text,
                "search_volume": idea.keyword_idea_metrics.avg_monthly_searches,
                "competition": str(idea.keyword_idea_metrics.competition),
                "competition_index": idea.keyword_idea_metrics.competition_index,
                "low_top_of_page_bid": round(low_top_of_page_bid, 2),
                "high_top_of_page_bid": round(high_top_of_page_bid, 2),
            })
        
        # Create visualization if requested and if we have data
        visualization_url = None
        if formatted_results and data.get('create_visualization', True):
            visualization_url = create_visualization(formatted_results)
        
        response_data = {"keyword_ideas": formatted_results}
        if visualization_url:
            response_data["visualization"] = visualization_url
            
        return jsonify(response_data)
        
    except GoogleAdsException as ex:
        error_message = f"Google Ads API error: {ex.error.code().name}"
        detail_message = ex.failure.errors[0].message if ex.failure.errors else str(ex)
        print(f"Request made: {ex}")  # Log the full error for debugging
        return jsonify({
            "error": error_message,
            "detail": detail_message
        }), 400
        
    except Exception as e:
        import traceback
        print(f"Unexpected error: {traceback.format_exc()}")  # Log the full error for debugging
        return jsonify({"error": str(e)}), 500

def generate_keyword_ideas(client, customer_id, keywords=None, language='en', location='US', page_url=None, competitors_domains=None):
    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
    
    # Map language codes to Google Ads language constants
    language_mapping = {
        "en": "languageConstants/1000",  # English
        "es": "languageConstants/1003",  # Spanish
        "fr": "languageConstants/1002",  # French
        "de": "languageConstants/1001",  # German
        "pt": "languageConstants/1014",  # Portuguese
        "it": "languageConstants/1004",  # Italian
        "ru": "languageConstants/1031",  # Russian
        "ja": "languageConstants/1005",  # Japanese
        "zh": "languageConstants/1017",  # Chinese (Simplified)
    }
    
    # Map location codes to Google Ads geo target constants
    # This is a simplification - for production, you might want to use the GeoTargetConstantService
    location_mapping = {
        "US": "geoTargetConstants/2840",  # United States
        "CA": "geoTargetConstants/2124",  # Canada
        "GB": "geoTargetConstants/2826",  # United Kingdom
        "AU": "geoTargetConstants/2036",  # Australia
        "DE": "geoTargetConstants/2276",  # Germany
        "FR": "geoTargetConstants/2250",  # France
        "ES": "geoTargetConstants/2724",  # Spain
    }
    
    # Build the request
    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id
    
    # Set the language properly
    if language in language_mapping:
        request.language = language_mapping[language]
    elif language.startswith("languageConstants/"):
        request.language = language
    else:
        # Default to English if not recognized
        request.language = "languageConstants/1000"
    
    # Set the location properly
    if location in location_mapping:
        request.geo_target_constants.append(location_mapping[location])
    elif location.startswith("geoTargetConstants/"):
        request.geo_target_constants.append(location)
    elif location:
        # Use a direct approach instead of SuggestGeoTargetConstantsRequest
        # For common country codes, use a predefined mapping
        # For US, default to US if no mapping is found
        request.geo_target_constants.append("geoTargetConstants/2840")  # Default to US
    
    # Set up the appropriate seed
    keyword_seed = None
    url_seed = None
    domain_seed = None
    
    # Add keywords if provided
    if keywords and len(keywords) > 0:
        keyword_seed = client.get_type("KeywordSeed")
        for keyword in keywords:
            keyword_seed.keywords.append(keyword)
        request.keyword_seed = keyword_seed
    
    # Add page URL if provided
    if page_url:
        url_seed = client.get_type("UrlSeed")
        url_seed.url = page_url
        request.url_seed = url_seed
    
    # Add competitor domains if provided
    if competitors_domains and len(competitors_domains) > 0:
        domain_seed = client.get_type("SiteSeed")
        for domain in competitors_domains:
            domain_seed.sites.append(domain)
        request.site_seed = domain_seed
    
    print(f"Sending request to Google Ads: {request}")  # Log the request for debugging
    
    # Get keyword ideas
    keyword_ideas = keyword_plan_idea_service.generate_keyword_ideas(request=request)
    
    return keyword_ideas

def create_visualization(keyword_data):
    # Convert to pandas DataFrame
    df = pd.DataFrame(keyword_data)
    
    # Create visualization
    plt.figure(figsize=(12, 6))
    
    # Sort by search_volume and take top 15 for readability
    df_sorted = df.sort_values('search_volume', ascending=False).head(15)
    
    # Plot
    plt.bar(df_sorted['text'], df_sorted['search_volume'])
    plt.xticks(rotation=45, ha='right')
    plt.xlabel('Keywords')
    plt.ylabel('Average Monthly Searches')
    plt.title('Keyword Popularity')
    plt.tight_layout()
    
    # Save to a base64 encoded string for embedding in response
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    
    graphic = base64.b64encode(image_png).decode('utf-8')
    return graphic

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
