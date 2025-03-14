from openai import OpenAI
import os
import time
import json
from supabase import create_client, Client

# Initialize the OpenAI client with your API key
client = OpenAI(api_key="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")

# Initialize Supabase client
# Replace with your Supabase URL and key
supabase_url = "https://zmhyhfmovzscafidawme.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InptaHloZm1vdnpzY2FmaWRhd21lIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDA2NjYzMjYsImV4cCI6MjA1NjI0MjMyNn0.cwm91hqel6tabhoANjxuEFDoBLNh2FaNN8uTc1j1oJU"
supabase: Client = create_client(supabase_url, supabase_key)

def extract_product_details(text):
    """
    Parse the AI response to extract structured product details.
    This is a simple implementation - you might need to adjust based on actual responses.
    """
    # Default structure
    details = {
        "description": "",
        "technical_details": "",
        "usage_instructions": ""
    }
    
    # Simple parsing logic - adjust as needed based on AI response patterns
    sections = text.split("\n\n")
    
    for section in sections:
        if "description" in section.lower():
            details["description"] = section
        elif "technical details" in section.lower() or "specifications" in section.lower():
            details["technical_details"] = section
        elif "usage" in section.lower() or "instructions" in section.lower() or "how to use" in section.lower():
            details["usage_instructions"] = section
    
    # If we couldn't find specific sections, use the whole text as description
    if not any(details.values()):
        details["description"] = text
        
    return details

def get_product_details(previous_response_id=None):
    product_name = input("Enter the product name: ")

    if not product_name.strip():
        print("You must enter a product name.")
        return previous_response_id

    print(f"Searching for information about '{product_name}'...")
    
    # Create the response with web search enabled
    response = client.responses.create(
        model="gpt-4o",
        input=f"Find a detailed product description, technical details, and usage instructions for '{product_name}' on MySkinRecipes.com. Format your response with clear sections for Description, Technical Details, and Usage Instructions.",
        previous_response_id=previous_response_id,
        tools=[{"type": "web_search"}]
    )
    
    # Wait for the response to complete if it's still processing
    response_id = response.id
    while response.status == "in_progress":
        print("Searching for product information...")
        time.sleep(2)
        response = client.responses.retrieve(response_id=response_id)
    
    # Extract the text content from the response
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
        print("No content available in the response.")
        return response_id
    
    # Display the information
    print("\n🔍 Product Information:\n")
    print(full_text)
    
    # Parse the text into structured data
    product_details = extract_product_details(full_text)
    
    # Store in Supabase
    try:
        data = {
            "product_name": product_name,
            "description": product_details["description"],
            "technical_details": product_details["technical_details"],
            "usage_instructions": product_details["usage_instructions"],
            "created_at": "now()"
        }
        
        result = supabase.table("products").insert(data).execute()
        
        if result.data:
            print("\n✅ Product information saved to database successfully!")
        else:
            print("\n❌ Failed to save product information to database.")
            
    except Exception as e:
        print(f"\n❌ Error saving to database: {str(e)}")
    
    return response_id

if __name__ == "__main__":
    response_id = None
    print("🌟 Product Information Fetcher 🌟")
    print("This tool searches for product information and stores it in your database.\n")
    
    while True:
        response_id = get_product_details(response_id)
        
        continue_search = input("\nWould you like to search for another product? (y/n): ")
        if continue_search.lower() != 'y':
            break
    
    print("\nThank you for using the Product Information Fetcher!")