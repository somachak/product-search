from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import time
from supabase import create_client, Client
import os

app = Flask(__name__)
# Update CORS configuration to be more permissive for testing
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Add this new route
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "Welcome to Product Search API",
        "endpoints": {
            "/search_product": "POST - Search for product information",
            "/search_ingredients": "POST - Search for ingredient information",
            "/console_test": "POST - Test the OpenAI API and print results to console"
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

def extract_ingredient_details(text):
    # Try to parse as JSON first
    import json
    try:
        # Check if the text contains valid JSON
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx]
            data = json.loads(json_str)
            
            # Ensure the suggested_products structure exists
            if 'suggested_products' not in data:
                data['suggested_products'] = {"ewg": [], "incidecoder": []}
            elif not isinstance(data['suggested_products'], dict):
                data['suggested_products'] = {"ewg": [], "incidecoder": []}
            
            # Ensure EWG and INCIDECODER keys exist
            if 'ewg' not in data['suggested_products']:
                data['suggested_products']['ewg'] = []
            if 'incidecoder' not in data['suggested_products']:
                data['suggested_products']['incidecoder'] = []
                
            return data
    except Exception as e:
        print(f"JSON parsing error: {e}")
        # If JSON parsing fails, continue with text parsing
    
    # Default structure
    details = {
        "description": "",
        "formulation_details": "",
        "technical_details": "",
        "product_page_link": "",
        "source_website": "",
        "suggested_products": {
            "ewg": [],
            "incidecoder": []
        }
    }
    
    # Split by sections
    sections = text.split('\n\n')
    
    for section in sections:
        section = section.strip()
        if not section:
            continue
            
        # Extract description
        if "description" in section.lower() and not details["description"]:
            details["description"] = section.split(":", 1)[1].strip() if ":" in section else section
        
        # Extract formulation details
        elif "formulation" in section.lower() and not details["formulation_details"]:
            details["formulation_details"] = section.split(":", 1)[1].strip() if ":" in section else section
        
        # Extract technical details
        elif "technical" in section.lower() and not details["technical_details"]:
            details["technical_details"] = section.split(":", 1)[1].strip() if ":" in section else section
        
        # Extract product page link
        elif ("link" in section.lower() or "url" in section.lower() or "http" in section.lower()) and not details["product_page_link"]:
            # Extract URL
            import re
            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', section)
            if urls:
                details["product_page_link"] = urls[0]
        
        # Extract source website
        elif "source" in section.lower() and not details["source_website"]:
            for line in section.split('\n'):
                if ":" in line and "source" in line.lower():
                    details["source_website"] = line.split(":", 1)[1].strip()
                    break
        
        # Extract EWG products
        elif "ewg" in section.lower():
            details["suggested_products"]["ewg"].append({
                "product_name": "EWG Product",
                "description": section
            })
        
        # Extract INCIDECODER products
        elif "incidecoder" in section.lower():
            details["suggested_products"]["incidecoder"].append({
                "product_name": "INCIDECODER Product",
                "description": section
            })
    
    return details

@app.route('/search_product', methods=['POST'])
def search_product():
    data = request.json
    product_name = data.get('product_name')
    
    if not product_name:
        return jsonify({"error": "Product name is required"}), 400
    
    try:
        # Check if product already exists in database
        existing = supabase.table("products").select("*").eq("product_name", product_name).eq("item_type", "product").execute()
        
        if existing.data:
            # Return existing data in the simplified format with three columns
            return jsonify({
                "success": True,
                "product": {
                    "name": existing.data[0]['product_name'],
                    "index": existing.data[0]['id'],
                    "text_description": existing.data[0]['description']
                },
                "source": "database"
            })
        
        # Rest of the OpenAI API call remains the same
        response = client.responses.create(
          model="gpt-4o",
          input=[
            {
              "role": "system",
              "content": [
                {
                  "type": "input_text",
                  "text": "Search for single or bulk ingredients provided by the user on myskinrecipes.com and return detailed descriptions, formulation information, and technical details. This includes usage rates, regional compliance, and links to the product page. Also, suggest popular products using these ingredients from EWG Skin Deep and INCIDECODER.com.\n\n# Steps\n\n1. **Input Capture**: Receive single or bulk ingredient names from the user.\n2. **Search and Retrieve**: Conduct searches for each ingredient on myskinrecipes.com.\n3. **Information Extraction**:\n   - Obtain detailed descriptions of each ingredient.\n   - Extract formulation details, including usage rates and recommended applications.\n   - Gather technical details such as regional compliance information.\n4. **Link Collection**: Provide a direct link to the product page for each ingredient on myskinrecipes.com.\n5. **Additional Product Suggestions**:\n   - Search EWG Skin Deep and INCIDECODER.com for popular products utilizing these ingredients.\n   - Compile a list of suggested products and provide relevant descriptions or ratings if available.\n\n# Output Format\n\nThe output should be structured in a JSON format with the following fields for each ingredient:\n- `ingredient_name`: The name of the ingredient.\n- `description`: A detailed description of the ingredient.\n- `formulation_details`: Information on formulation, including usage rates.\n- `technical_details`: Information on regional compliance and technical specifications.\n- `product_page_link`: URL to the myskinrecipes.com product page.\n- `suggested_products`: \n  - `ewg`: A list of popular products from EWG Skin Deep including descriptions or ratings.\n  - `incidecoder`: A list of popular products from INCIDECODER.com including descriptions or ratings.\n\n# Examples\n\n### Example Input\n```json\n{\n  \"ingredients\": [\"Ingredient A\", \"Ingredient B\"]\n}\n```\n\n### Example Output\n```json\n[\n  {\n    \"ingredient_name\": \"Ingredient A\",\n    \"description\": \"Detailed description of Ingredient A.\",\n    \"formulation_details\": \"Usage rate and recommendations for Ingredient A.\",\n    \"technical_details\": \"Regional compliance information for Ingredient A.\",\n    \"product_page_link\": \"https://www.myskinrecipes.com/ingredientA\",\n    \"suggested_products\": {\n      \"ewg\": [\n        {\n          \"product_name\": \"Product 1\",\n          \"description\": \"Details about Product 1 using Ingredient A.\"\n        }\n      ],\n      \"incidecoder\": [\n        {\n          \"product_name\": \"Product 2\",\n          \"description\": \"Details about Product 2 using Ingredient A.\"\n        }\n      ]\n    }\n  },\n  {\n    \"ingredient_name\": \"Ingredient B\",\n    \"description\": \"Detailed description of Ingredient B.\",\n    \"formulation_details\": \"Usage rate and recommendations for Ingredient B.\",\n    \"technical_details\": \"Regional compliance information for Ingredient B.\",\n    \"product_page_link\": \"https://www.myskinrecipes.com/ingredientB\",\n    \"suggested_products\": {\n      \"ewg\": [\n        {\n          \"product_name\": \"Product 3\",\n          \"description\": \"Details about Product 3 using Ingredient B.\"\n        }\n      ],\n      \"incidecoder\": [\n        {\n          \"product_name\": \"Product 4\",\n          \"description\": \"Details about Product 4 using Ingredient B.\"\n        }\n      ]\n    }\n  }\n]\n```\n\n# Notes\n\n- Ensure that all information is retrieved and presented accurately.\n- Use available APIs or scraping methods within legal and ethical bounds.\n- Provide comprehensive and concise descriptions and details for user clarity."
                }
              ]
            }
          ],
          text={
            "format": {
              "type": "text"
            }
          },
          reasoning={},
          tools=[
            {
              "type": "web_search_preview",
              "user_location": {
                "type": "approximate"
              },
              "search_context_size": "medium"
            }
          ],
          temperature=1,
          max_output_tokens=2048,
          top_p=1,
          store=True
        )
        
        # Extract the text content
        full_text = response.text
        
        if not full_text:
            return jsonify({"error": "No information available for this product. Please check the spelling or try a different product."}), 404
        
        # Check if the response indicates the product wasn't found
        if "not found" in full_text.lower() or "couldn't find" in full_text.lower() or "no information" in full_text.lower() or "unable to find" in full_text.lower():
            return jsonify({
                "success": False,
                "error": "Product not found. Please check the spelling or try a different product."
            }), 404
        
        # Parse the text into structured data
        product_details = extract_product_details(full_text)
        
        # Store in Supabase only if we have meaningful data
        if any(product_details.values()):
            # Simplified data structure with only 3 columns
            data = {
                "product_name": product_name,
                "description": product_details["description"],
                "item_type": "product"  # Keep this to distinguish between products and ingredients
            }
            
            result = supabase.table("products").insert(data).execute()
            
            if not result.data:
                return jsonify({"error": "Failed to save product to database"}), 500
                
            # Return the product details to the client with only 3 columns
            return jsonify({
                "success": True,
                "product": {
                    "name": product_name,
                    "index": result.data[0]['id'],
                    "text_description": product_details["description"]
                },
                "source": "api"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Could not extract meaningful information about this product. Please check the spelling or try a different product."
            }), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/search_ingredients', methods=['POST'])
def search_ingredients():
    data = request.json
    ingredients = data.get('ingredients', [])
    
    if not ingredients:
        return jsonify({"error": "At least one ingredient is required"}), 400
    
    try:
        results = []
        raw_responses = {}
        not_found = []
        
        for ingredient in ingredients:
            ingredient_found = False
            ingredient_details = {}
            search_source = "None"
            raw_response = ""
            
            # Define search tiers
            search_tiers = [
                {
                    "name": "Cosmetic Ingredient Sites",
                    "sites": ["myskinrecipes.com", "makingcosmetics.com", "lotioncrafter.com"]
                },
                {
                    "name": "General Cosmetic Resources",
                    "sites": ["cosmeticsinfo.org", "ewg.org", "incidecoder.com"]
                },
                {
                    "name": "Scientific Sources",
                    "sites": ["pubmed.ncbi.nlm.nih.gov", "scholar.google.com"]
                }
            ]
            
            # Try each search tier until we find information
            for tier in search_tiers:
                if ingredient_found:
                    break
                
                # Create search prompt for this tier
                sites_str = ", ".join(tier["sites"])
                system_prompt = f"You are a cosmetic formulation assistant. Search for detailed information about cosmetic ingredients primarily on these sites: {sites_str}. Provide comprehensive details about each ingredient."
                
                user_prompt = f"Please provide detailed information about the cosmetic ingredient '{ingredient}', including:\n\n1. A detailed description of what it is and its purpose in cosmetic formulations\n2. Formulation details including recommended usage rates\n3. Technical details such as solubility, pH, and regional compliance information\n4. A direct link to the product page\n5. Popular products using this ingredient from EWG Skin Deep and INCIDECODER.com\n\nFormat your response in a structured way with clear headings for each section."
                
                try:
                    # Make the API call
                    response = client.chat.completions.create(
                        model="gpt-4o-search-preview",
                        web_search_options={
                            "search_context_size": "high",
                        },
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    )
                    
                    # Extract the text content
                    full_text = response.choices[0].message.content
                    raw_response = full_text
                    
                    # Extract citations if available
                    citations = []
                    if hasattr(response.choices[0].message, 'annotations'):
                        for annotation in response.choices[0].message.annotations:
                            if annotation.type == "url_citation" and hasattr(annotation, 'url_citation'):
                                citations.append({
                                    "url": annotation.url_citation.url,
                                    "title": annotation.url_citation.title
                                })
                except Exception as api_error:
                    print(f"OpenAI API error for ingredient '{ingredient}': {api_error}")
                    continue  # Skip to the next tier
                
                if not full_text or "ingredient not found" in full_text.lower() or "not found" in full_text.lower() or "couldn't find" in full_text.lower():
                    # If not found in this tier, continue to next tier
                    continue
                
                # Parse the text into structured data
                try:
                    # Create a more structured parsing approach
                    import re
                    
                    # Initialize the structured data
                    parsed_details = {
                        "ingredient_name": ingredient,
                        "description": "",
                        "formulation_details": "",
                        "technical_details": "",
                        "product_page_link": "",
                        "source_website": "",
                        "search_tier": tier["name"],
                        "suggested_products": {
                            "ewg": [],
                            "incidecoder": []
                        }
                    }
                    
                    # Extract sections using regex patterns
                    description_match = re.search(r'(?i)description:?\s*(.*?)(?=\n\n|formulation|technical|product page|suggested products|$)', full_text, re.DOTALL)
                    if description_match:
                        parsed_details["description"] = description_match.group(1).strip()
                    
                    formulation_match = re.search(r'(?i)formulation details:?\s*(.*?)(?=\n\n|description|technical|product page|suggested products|$)', full_text, re.DOTALL)
                    if formulation_match:
                        parsed_details["formulation_details"] = formulation_match.group(1).strip()
                    
                    technical_match = re.search(r'(?i)technical details:?\s*(.*?)(?=\n\n|description|formulation|product page|suggested products|$)', full_text, re.DOTALL)
                    if technical_match:
                        parsed_details["technical_details"] = technical_match.group(1).strip()
                    
                    # Extract product page link
                    link_match = re.search(r'(?i)product page link:?\s*(.*?)(?=\n\n|description|formulation|technical|suggested products|$)', full_text, re.DOTALL)
                    if link_match:
                        link_text = link_match.group(1).strip()
                        url_match = re.search(r'https?://[^\s<>"]+|www\.[^\s<>"]+', link_text)
                        if url_match:
                            parsed_details["product_page_link"] = url_match.group(0)
                    
                    # If no product link found in the text, use citations
                    if not parsed_details["product_page_link"] and citations:
                        parsed_details["product_page_link"] = citations[0]["url"]
                    
                    # Extract source website
                    source_match = re.search(r'(?i)source website:?\s*(.*?)(?=\n\n|description|formulation|technical|product page|suggested products|$)', full_text, re.DOTALL)
                    if source_match:
                        parsed_details["source_website"] = source_match.group(1).strip()
                    else:
                        # If no source website found, use the first site from the tier
                        parsed_details["source_website"] = tier["sites"][0] if tier["sites"] else "Unknown"
                    
                    # Extract suggested products
                    suggested_match = re.search(r'(?i)suggested products:?\s*(.*?)(?=\n\n|$)', full_text, re.DOTALL)
                    if suggested_match:
                        suggested_text = suggested_match.group(1).strip()
                        
                        # Process EWG products
                        ewg_section = re.search(r'(?i)from ewg.*?:(.*?)(?=from incidecoder|$)', suggested_text, re.DOTALL)
                        if ewg_section:
                            ewg_text = ewg_section.group(1).strip()
                            ewg_products = re.findall(r'(?i)(.*?):\s*(.*?)(?=\n|$)', ewg_text)
                            for product_name, description in ewg_products:
                                parsed_details["suggested_products"]["ewg"].append({
                                    "product_name": product_name.strip(),
                                    "description": description.strip()
                                })
                        
                        # Process INCIDECODER products
                        incidecoder_section = re.search(r'(?i)from incidecoder.*?:(.*?)(?=from ewg|$)', suggested_text, re.DOTALL)
                        if incidecoder_section:
                            incidecoder_text = incidecoder_section.group(1).strip()
                            incidecoder_products = re.findall(r'(?i)(.*?):\s*(.*?)(?=\n|$)', incidecoder_text)
                            for product_name, description in incidecoder_products:
                                parsed_details["suggested_products"]["incidecoder"].append({
                                    "product_name": product_name.strip(),
                                    "description": description.strip()
                                })
                    
                    # Check if we have meaningful data
                    has_data = parsed_details.get("description", "") or parsed_details.get("formulation_details", "") or parsed_details.get("technical_details", "")
                    
                    if has_data:
                        ingredient_found = True
                        ingredient_details = parsed_details
                        search_source = tier["name"]
                        raw_responses[ingredient] = raw_response
                        
                        # Skip database operations
                        results.append({
                            "name": ingredient,
                            "index": "N/A (Database bypassed)",
                            "text_description": ingredient_details.get("description", ""),
                            "formulation_details": ingredient_details.get("formulation_details", ""),
                            "technical_details": ingredient_details.get("technical_details", ""),
                            "product_page_link": ingredient_details.get("product_page_link", ""),
                            "search_tier": search_source
                        })
                except Exception as e:
                    print(f"Error parsing ingredient details: {e}")
                    continue
            
            # If ingredient was not found in any tier
            if not ingredient_found:
                not_found.append(ingredient)
        
        # Return all ingredient details to the client
        response_data = {
            "success": True,
            "ingredients": results,
            "raw_responses": raw_responses
        }
        
        if not_found:
            response_data["not_found"] = not_found
            response_data["message"] = "Some ingredients were not found. Please check spelling or try different ingredients."
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/console_test', methods=['POST'])
def console_test():
    data = request.json
    ingredient = data.get('ingredient')
    
    if not ingredient:
        return jsonify({"error": "Ingredient name is required"}), 400
    
    try:
        print(f"\n{'='*80}")
        print(f"TESTING OPENAI API WITH INGREDIENT: {ingredient}")
        print(f"{'='*80}\n")
        
        # Use the responses.create API
        response = client.responses.create(
          model="gpt-4o",
          input=[
            {
              "role": "system",
              "content": [
                {
                  "type": "input_text",
                  "text": "Search for single or bulk ingredients provided by the user on myskinrecipes.com and return detailed descriptions, formulation information, and technical details. This includes usage rates, regional compliance, and links to the product page. Also, suggest popular products using these ingredients from EWG Skin Deep and INCIDECODER.com.\n\n# Steps\n\n1. **Input Capture**: Receive single or bulk ingredient names from the user.\n2. **Search and Retrieve**: Conduct searches for each ingredient on myskinrecipes.com.\n3. **Information Extraction**:\n   - Obtain detailed descriptions of each ingredient.\n   - Extract formulation details, including usage rates and recommended applications.\n   - Gather technical details such as regional compliance information.\n4. **Link Collection**: Provide a direct link to the product page for each ingredient on myskinrecipes.com.\n5. **Additional Product Suggestions**:\n   - Search EWG Skin Deep and INCIDECODER.com for popular products utilizing these ingredients.\n   - Compile a list of suggested products and provide relevant descriptions or ratings if available.\n\n# Output Format\n\nThe output should be structured in a JSON format with the following fields for each ingredient:\n- `ingredient_name`: The name of the ingredient.\n- `description`: A detailed description of the ingredient.\n- `formulation_details`: Information on formulation, including usage rates.\n- `technical_details`: Information on regional compliance and technical specifications.\n- `product_page_link`: URL to the myskinrecipes.com product page.\n- `suggested_products`: \n  - `ewg`: A list of popular products from EWG Skin Deep including descriptions or ratings.\n  - `incidecoder`: A list of popular products from INCIDECODER.com including descriptions or ratings.\n\n# Examples\n\n### Example Input\n```json\n{\n  \"ingredients\": [\"Ingredient A\", \"Ingredient B\"]\n}\n```\n\n### Example Output\n```json\n[\n  {\n    \"ingredient_name\": \"Ingredient A\",\n    \"description\": \"Detailed description of Ingredient A.\",\n    \"formulation_details\": \"Usage rate and recommendations for Ingredient A.\",\n    \"technical_details\": \"Regional compliance information for Ingredient A.\",\n    \"product_page_link\": \"https://www.myskinrecipes.com/ingredientA\",\n    \"suggested_products\": {\n      \"ewg\": [\n        {\n          \"product_name\": \"Product 1\",\n          \"description\": \"Details about Product 1 using Ingredient A.\"\n        }\n      ],\n      \"incidecoder\": [\n        {\n          \"product_name\": \"Product 2\",\n          \"description\": \"Details about Product 2 using Ingredient A.\"\n        }\n      ]\n    }\n  },\n  {\n    \"ingredient_name\": \"Ingredient B\",\n    \"description\": \"Detailed description of Ingredient B.\",\n    \"formulation_details\": \"Usage rate and recommendations for Ingredient B.\",\n    \"technical_details\": \"Regional compliance information for Ingredient B.\",\n    \"product_page_link\": \"https://www.myskinrecipes.com/ingredientB\",\n    \"suggested_products\": {\n      \"ewg\": [\n        {\n          \"product_name\": \"Product 3\",\n          \"description\": \"Details about Product 3 using Ingredient B.\"\n        }\n      ],\n      \"incidecoder\": [\n        {\n          \"product_name\": \"Product 4\",\n          \"description\": \"Details about Product 4 using Ingredient B.\"\n        }\n      ]\n    }\n  }\n]\n```\n\n# Notes\n\n- Ensure that all information is retrieved and presented accurately.\n- Use available APIs or scraping methods within legal and ethical bounds.\n- Provide comprehensive and concise descriptions and details for user clarity."
                }
              ]
            },
            {
              "role": "user",
              "content": [
                {
                  "type": "input_text",
                  "text": ingredient
                }
              ]
            }
          ],
          text={
            "format": {
              "type": "text"
            }
          },
          reasoning={},
          tools=[
            {
              "type": "web_search_preview",
              "user_location": {
                "type": "approximate"
              },
              "search_context_size": "medium"
            }
          ],
          temperature=1,
          max_output_tokens=2048,
          top_p=1,
          store=True
        )
        
        # Print the raw response to console
        print("\nRAW RESPONSE:")
        print(f"{'='*80}")
        print(response.text)
        print(f"{'='*80}\n")
        
        # Try to parse as JSON if possible
        try:
            # Look for JSON structure in the response
            import re
            import json
            json_match = re.search(r'```json\n(.*?)\n```', response.text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                parsed_json = json.loads(json_str)
                print("\nPARSED JSON:")
                print(f"{'='*80}")
                print(json.dumps(parsed_json, indent=2))
                print(f"{'='*80}\n")
                
                return jsonify({
                    "success": True,
                    "raw_response": response.text,
                    "parsed_json": parsed_json
                })
        except Exception as json_error:
            print(f"JSON parsing error: {json_error}")
        
        return jsonify({
            "success": True,
            "raw_response": response.text
        })
        
    except Exception as e:
        error_message = str(e)
        print(f"\nERROR: {error_message}")
        return jsonify({"error": error_message}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    # Add additional error handling and logging
    try:
        print(f"Starting server on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"Error starting server: {e}")