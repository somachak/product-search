from flask import Flask, request, jsonify
from openai import OpenAI
import time
from supabase import create_client, Client
import os

app = Flask(__name__)

# Add this new route
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "Welcome to Product Search API",
        "endpoints": {
            "/search_product": "POST - Search for product information"
        }
    })

# Initialize OpenAI client with your API key directly
client = OpenAI(api_key="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")

# Initialize Supabase client with your credentials directly
supabase_url = "https://zmhyhfmovzscafidawme.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InptaHloZm1vdnpzY2FmaWRhd21lIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDA2NjYzMjYsImV4cCI6MjA1NjI0MjMyNn0.cwm91hqel6tabhoANjxuEFDoBLNh2FaNN8uTc1j1oJU"
supabase = create_client(supabase_url, supabase_key)

def extract_product_details(text):
    """Parse the AI response to extract structured product details."""
    details = {
        "description": "",
        "technical_details": "",
        "usage_instructions": ""
    }
    
    sections = text.split("\n\n")
    
    for section in sections:
        if "description" in section.lower():
            details["description"] = section
        elif "technical details" in section.lower() or "specifications" in section.lower():
            details["technical_details"] = section
        elif "usage" in section.lower() or "instructions" in section.lower() or "how to use" in section.lower():
            details["usage_instructions"] = section
    
    if not any(details.values()):
        details["description"] = text
        
    return details

@app.route('/search_product', methods=['POST'])
def search_product():
    data = request.json
    product_name = data.get('product_name')
    
    if not product_name:
        return jsonify({"error": "Product name is required"}), 400
    
    try:
        # Create the response with web search enabled
        response = client.responses.create(
            model="gpt-4o",
            input=f"Find a detailed product description, technical details, and usage instructions for '{product_name}' on MySkinRecipes.com. Format your response with clear sections for Description, Technical Details, and Usage Instructions.",
            tools=[{"type": "web_search"}]
        )
        
        # Wait for the response to complete
        response_id = response.id
        while response.status == "in_progress":
            time.sleep(2)
            response = client.responses.retrieve(response_id=response_id)
        
        # Extract the text content
        full_text = ""
        if hasattr(response, 'output') and response.output:
            for output_item in response.output:
                if hasattr(output_item, 'content') and output_item.content:
                    for content_item in output_item.content:
                        if hasattr(content_item, 'text'):
                            full_text += content_item.text + "\n"
                elif hasattr(output_item, 'text'):
                    full_text += output_item.text + "\n"
        
        if not full_text:
            return jsonify({"error": "No content available in the response"}), 404
        
        # Parse the text into structured data
        product_details = extract_product_details(full_text)
        
        # Store in Supabase
        data = {
            "product_name": product_name,
            "description": product_details["description"],
            "technical_details": product_details["technical_details"],
            "usage_instructions": product_details["usage_instructions"],
            "created_at": "now()"
        }
        
        result = supabase.table("products").insert(data).execute()
        
        if not result.data:
            return jsonify({"error": "Failed to save product to database"}), 500
            
        # Return the product details to the client
        return jsonify({
            "success": True,
            "product": {
                "id": result.data[0]['id'],
                "name": product_name,
                "description": product_details["description"],
                "technical_details": product_details["technical_details"],
                "usage_instructions": product_details["usage_instructions"]
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)