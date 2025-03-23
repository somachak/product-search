from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import time
from supabase import create_client, Client
import os

app = Flask(__name__)
# Enable CORS with more specific settings
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": "*", "expose_headers": "*"}})

# Add this new route
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "Welcome to Product Search API",
        "endpoints": {
            "/search_product": "POST - Search for product information",
            "/search_ingredients": "POST - Search for ingredient information"
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
            # Return existing data if found
            return jsonify({
                "success": True,
                "product": existing.data[0],
                "source": "database"
            })
        
        # Updated OpenAI API call
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a product information specialist."},
                {"role": "user", "content": f"Find a detailed product description, technical details, and usage instructions for '{product_name}' on MySkinRecipes.com. Format your response with clear sections for Description, Technical Details, and Usage Instructions."}
            ]
        )
        
        # Extract the text content
        full_text = response.choices[0].message.content
        
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
            data = {
                "product_name": product_name,
                "description": product_details["description"],
                "technical_details": product_details["technical_details"],
                "usage_instructions": product_details["usage_instructions"],
                "item_type": "product",  # Add item type to distinguish between products and ingredients
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
                    "usage_instructions": product_details["usage_instructions"],
                    "item_type": "product"
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
    
    results = []
    not_found = []
    
    # Define the search tiers
    search_tiers = [
        {
            "name": "Primary Sources",
            "sites": ["myskinrecipes.com"]
        },
        {
            "name": "Secondary Sources",
            "sites": [
                "theformulary.co.uk", 
                "aromantic.co.uk", 
                "mysticmomentsuk.com", 
                "thesoapery.co.uk", 
                "thesoapkitchen.co.uk", 
                "suppliesforcandles.co.uk", 
                "hybridingredients.co.uk", 
                "naturallythinking.com", 
                "bayhousearomantics.com", 
                "alexmo-cosmetics.de", 
                "naturallybalmy.co.uk"
            ]
        },
        {
            "name": "Tertiary Sources",
            "sites": ["Specialchem", "ULProspector"]
        }
    ]
    
    try:
        for ingredient in ingredients:
            # Check if ingredient already exists in database
            existing = supabase.table("products").select("*").eq("product_name", ingredient).eq("item_type", "ingredient").execute()
            
            if existing.data:
                # Return existing data if found
                results.append(existing.data[0])
                continue
            
            # Initialize variables to track search success
            ingredient_found = False
            search_source = ""
            ingredient_details = None
            
            # Try each search tier until ingredient is found
            for tier in search_tiers:
                if ingredient_found:
                    break
                
                sites_list = ", ".join(tier["sites"])
                
                # Using the exact system prompt from the playground
                system_prompt = """Search for single or bulk ingredients provided by the user on myskinrecipes.com and return detailed descriptions, formulation information, and technical details. This includes usage rates, regional compliance, and links to the product page. Also, suggest popular products using these ingredients from EWG Skin Deep and INCIDECODER.com."""
                
                # Using the exact user prompt structure from the playground
                user_prompt = f"""Search for detailed information about the ingredient '{ingredient}' on the following websites: {sites_list}.

Please provide:
1. A detailed description of the ingredient
2. Formulation details including usage rates and recommended applications
3. Technical details such as regional compliance information
4. A direct link to the product page
5. Popular products using this ingredient from EWG Skin Deep and INCIDECODER.com

Format your response in a structured way with clear headings for each section."""
                
                # Make the API call with the exact prompts from playground
                response = client.chat.completions.create(
                    model="gpt-4o-search-preview",
                    web_search_options={
                        "search_context_size": "high",
                    },
                    # Remove the temperature parameter as it's causing the error
                    # temperature=0.7,  # Match playground settings
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                
                # Extract the text content
                full_text = response.choices[0].message.content
                
                # Extract citations if available
                citations = []
                if hasattr(response.choices[0].message, 'annotations'):
                    for annotation in response.choices[0].message.annotations:
                        if annotation.type == "url_citation" and hasattr(annotation, 'url_citation'):
                            citations.append({
                                "url": annotation.url_citation.url,
                                "title": annotation.url_citation.title
                            })
                
                if not full_text or "ingredient not found" in full_text.lower() or "not found" in full_text.lower() or "couldn't find" in full_text.lower():
                    # If not found in this tier, continue to next tier
                    continue
                
                # Parse the text into structured data - improved parsing
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
                        
                        # Store in database
                        import json
                        data = {
                            "product_name": ingredient,
                            "description": ingredient_details.get("description", ""),
                            "technical_details": ingredient_details.get("technical_details", ""),
                            "usage_instructions": "",  # Not directly mapped in our new structure
                            "formulation_details": ingredient_details.get("formulation_details", ""),
                            "product_page_link": ingredient_details.get("product_page_link", ""),
                            "source_website": ingredient_details.get("source_website", ""),
                            "search_tier": ingredient_details.get("search_tier", ""),
                            "suggested_products": json.dumps(ingredient_details.get("suggested_products", {"ewg": [], "incidecoder": []})),
                            "item_type": "ingredient",
                            "created_at": "now()"
                        }
                        
                        # Insert into database
                        result = supabase.table("products").insert(data).execute()
                        
                        if result.data:
                            # Add to results
                            results.append(result.data[0])
                        else:
                            not_found.append(ingredient)
                except Exception as e:
                    print(f"Error parsing ingredient details: {e}")
                    continue
            
            # If ingredient was not found in any tier
            if not ingredient_found:
                not_found.append(ingredient)
        
        # Return all ingredient details to the client
        response_data = {
            "success": True,
            "ingredients": results
        }
        
        if not_found:
            response_data["not_found"] = not_found
            response_data["message"] = "Some ingredients were not found. Please check spelling or try different ingredients."
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    # Add additional error handling and logging
    try:
        print(f"Starting server on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"Error starting server: {e}")