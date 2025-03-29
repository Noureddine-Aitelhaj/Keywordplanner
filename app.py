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
        language_id = data.get('language_id', '1000')  # Default English
        country_code = data.get('country_code', 'US')  # Default US
        
        if not customer_id or not keywords:
            return jsonify({"error": "Missing required parameters: customer_id and keywords"}), 400
        
        # Get client
        client = get_google_ads_client()
        
        # Get keyword ideas using the client
        keyword_ideas = generate_keyword_ideas(
            client,
            customer_id,
            keywords,
            language_id,
            country_code
        )
        
        # Format the response
        formatted_results = []
        for idea in keyword_ideas:
            formatted_results.append({
                "text": idea.text,
                "avg_monthly_searches": idea.keyword_idea_metrics.avg_monthly_searches,
                "competition": str(idea.keyword_idea_metrics.competition),
                "competition_index": idea.keyword_idea_metrics.competition_index,
                "low_top_of_page_bid_micros": idea.keyword_idea_metrics.low_top_of_page_bid_micros,
                "high_top_of_page_bid_micros": idea.keyword_idea_metrics.high_top_of_page_bid_micros,
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
        return jsonify({
            "error": error_message,
            "detail": detail_message
        }), 400
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_keyword_ideas(client, customer_id, keywords, language_id, country_code):
    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
    
    # Build the request
    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id
    request.language = language_id
    
    # Add the keywords
    request.keyword_seed.keywords.extend(keywords)
    
    # Set geographical locations (country)
    geo_target_constant_service = client.get_service("GeoTargetConstantService")
    gtc_request = client.get_type("SuggestGeoTargetConstantsRequest")
    gtc_request.location_names.names.append(country_code)
    response = geo_target_constant_service.suggest_geo_target_constants(gtc_request)
    
    geo_target_constant = response.geo_target_constant_suggestions[0].geo_target_constant
    request.geo_target_constants.append(geo_target_constant.resource_name)
    
    # Get keyword ideas
    keyword_ideas = keyword_plan_idea_service.generate_keyword_ideas(request=request)
    
    return keyword_ideas

def create_visualization(keyword_data):
    # Convert to pandas DataFrame
    df = pd.DataFrame(keyword_data)
    
    # Create visualization
    plt.figure(figsize=(12, 6))
    
    # Sort by avg_monthly_searches and take top 15 for readability
    df_sorted = df.sort_values('avg_monthly_searches', ascending=False).head(15)
    
    # Plot
    plt.bar(df_sorted['text'], df_sorted['avg_monthly_searches'])
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