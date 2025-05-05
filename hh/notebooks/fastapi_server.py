  
from fastapi import FastAPI, HTTPException  
from pydantic import BaseModel  
from typing import Optional, Dict, Any, List, Union  
import uvicorn  
import json  
import dspy  
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
print(f"API Key: {api_key}")


# Your load_optimized_prompt function  
def load_optimized_prompt(filename="optimized_prompt.json"):  
    with open(filename, "r") as f:  
        data = json.load(f)  

    instructions = data["instructions"]  

    demos = []  
    for demo_dict in data["demos"]:  
        example = dspy.Example(**demo_dict)  
        demos.append(example)  

    return instructions, demos  

# Define request and response models  
class ReviewRequest(BaseModel):  
    review: str  

class ReviewResponse(BaseModel):  
    sentiment: Optional[str] = None  
    key_features: Optional[Union[List[str], str]] = None  
    raw_result: Optional[str] = None  
    error: Optional[str] = None  

# Initialize FastAPI app  
app = FastAPI(  
    title="Review Analysis API",  
    description="API for analyzing product reviews using optimized DSPy prompts",  
    version="1.0.0"  
)  

# Load the optimized prompt at startup  
instructions, demos = load_optimized_prompt()  

def format_prompt_for_openai(instructions, demos, new_review):  
    """  
    Format the instructions and demos into a prompt for OpenAI API.  
      
    Args:  
        instructions: The optimized instructions  
        demos: List of few-shot examples  
        new_review: The new review to analyze  
          
    Returns:  
        str: Formatted prompt  
    """  
    prompt = f"{instructions}\n\n"  
      
    if demos:  
        prompt += "Examples:\n\n"  
        for demo in demos:  
            prompt += f"Input: {demo.review}\n"  
              
            # Safely access sentiment  
            sentiment = getattr(demo, 'sentiment', 'N/A')  
              
            # Safely access key_features with fallbacks  
            if hasattr(demo, 'key_features'):  
                features = demo.key_features  
            elif hasattr(demo, 'features'):  
                features = demo.features  
            elif hasattr(demo, 'features_mentioned'):  
                features = demo.features_mentioned  
            else:  
                # Use a default value if no attribute is found  
                features = 'N/A'  
                  
            prompt += f"Output: Sentiment: {sentiment}, Key Features: {features}\n\n"  
      
    prompt += f"Input: {new_review}\n"  
    prompt += "Output:"  
      
    return prompt

def analyze_review_with_openai(instructions, demos, new_review, model="gpt-4o-mini"):  
    try:  
        # Format the prompt  
        system_prompt = format_prompt_for_openai(instructions, demos, new_review)  
          
        # Initialize the OpenAI client  
        from openai import OpenAI  
        client = OpenAI()  
          
        # Call OpenAI API with the new format  
        response = client.chat.completions.create(  
            model=model,  
            messages=[  
                {"role": "system", "content": system_prompt}  
            ],  
            temperature=0.0  
        )  
          
        # Extract the response  
        result = response.choices[0].message.content  
        print(f"Raw API response: {result}")  
          
        # Parse the result - improved to handle multiple formats  
        try:  
            # Try to find JSON in the response  
            import re  
            import json  
              
            # Look for JSON pattern  
            json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)  
            if json_match:  
                # Extract and parse JSON  
                json_str = json_match.group(1)  
                data = json.loads(json_str)  
                return {  
                    "sentiment": data.get("sentiment", "N/A"),  
                    "key_features": data.get("key_features", "N/A")  
                }  
              
            # Try the original format as fallback  
            parts = result.split(', Key Features: ')  
            if len(parts) >= 2:  
                sentiment = parts[0].replace('Sentiment: ', '')  
                key_features = parts[1]  
                return {  
                    "sentiment": sentiment,  
                    "key_features": key_features  
                }  
                  
            # If we get here, try to extract sentiment and key_features from anywhere in the text  
            sentiment_match = re.search(r'sentiment["\s:]+([^",\n]+)', result.lower())  
            features_match = re.search(r'key_features["\s:]+(\[[^\]]+\])', result.lower())  
              
            sentiment = sentiment_match.group(1).strip() if sentiment_match else "N/A"  
            features = features_match.group(1).strip() if features_match else "N/A"  
              
            return {  
                "sentiment": sentiment,  
                "key_features": features  
            }  
              
        except Exception as e:  
            print(f"Error parsing response: {e}")  
            return {"raw_result": result}  
              
    except Exception as e:  
        print(f"Error calling OpenAI API: {e}")  
        return {"error": str(e)}

@app.post("/analyze", response_model=ReviewResponse)  
async def analyze_review(request: ReviewRequest):  
    if not request.review:  
        raise HTTPException(status_code=400, detail="No review provided")  

    # Analyze the review using the optimized prompt  
    result = analyze_review_with_openai(instructions, demos, request.review)  

    return result  

if __name__ == "__main__":  
    uvicorn.run(app, host="0.0.0.0", port=8000)  
