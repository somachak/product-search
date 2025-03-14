from openai import OpenAI
import os
import time

# Initialize the client with your API key
client = OpenAI(api_key="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")

def get_product_details(previous_response_id=None):
    product_name = input("Enter the product name: ")

    if not product_name.strip():
        print("You must enter a product name.")
        return

    # Create the response with web search enabled
    response = client.responses.create(
        model="gpt-4o",
        input=f"Find a detailed product description, technical details, and usage instructions for '{product_name}' on MySkinRecipes.com.",
        previous_response_id=previous_response_id,
        tools=[{"type": "web_search"}]
    )
    
    # Wait for the response to complete if it's still processing
    response_id = response.id
    while response.status == "in_progress":
        print("Searching for product information...")
        time.sleep(2)
        response = client.responses.retrieve(response_id=response_id)
    
    # Access the response content correctly
    print("\n🔍 Product Information:\n")
    
    # Debug the response structure
    print(f"Response status: {response.status}")
    
    # Extract the text content from the response
    if hasattr(response, 'output') and response.output:
        for output_item in response.output:
            if hasattr(output_item, 'content') and output_item.content:
                for content_item in output_item.content:
                    if hasattr(content_item, 'text'):
                        print(content_item.text)
            # Handle other potential content types
            elif hasattr(output_item, 'text'):
                print(output_item.text)
    else:
        print("No content available in the response.")
    
    return response.id

if __name__ == "__main__":
    response_id = None
    while True:
        response_id = get_product_details(response_id)
        
        continue_search = input("\nWould you like to search for another product? (y/n): ")
        if continue_search.lower() != 'y':
            break