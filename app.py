from flask import Flask, request, jsonify
import pandas as pd
from flask_cors import CORS
from llama_index.llms.ibm import WatsonxLLM
import os
import requests
import textwrap

os.environ["WATSONX_APIKEY"] ='cUAOZe81kVuhSVudBOGHSQHyORnpMPHZzL1bwwVUEuFT'

app = Flask(__name__)
app.name = "CodeGeneratorApp"
CORS(app)

# apikey='cUAOZe81kVuhSVudBOGHSQHyORnpMPHZzL1bwwVUEuFT'

# credentials = {
# "url": "https://us-south.ml.cloud.ibm.com",
# "apikey":apikey
# }import requests
requests.packages.urllib3.disable_warnings()
requests.adapters.DEFAULT_RETRIES = 5
s = requests.session()
s.keep_alive = False

os.environ["WATSONX_APIKEY"] ='cUAOZe81kVuhSVudBOGHSQHyORnpMPHZzL1bwwVUEuFT'
temperature = 0.5
max_new_tokens = 500
additional_params = {
    "decoding_method": "sample",
    "min_new_tokens": 1,
    "top_k": 50,
    "top_p": 1,
}

watsonx_llm = WatsonxLLM(
    model_id="meta-llama/llama-3-70b-instruct",
    url="https://us-south.ml.cloud.ibm.com",
    project_id="8c02f540-b106-4311-b7a9-4afde1ddb4bb",
    temperature=temperature,
    max_new_tokens=max_new_tokens,
    additional_params=additional_params,
    session=s
)

def generate_code(query, file_path, columns):
    # prompt = f"""[INST]
    # You are a Python programmer. Write Python code for {query} only that must start with // and end with // always and
    # don't include ```python inside // and also any other text not included in //.
    # and without any explanation to perform the following task: {query}.
    # Like below output format always without any explanation and without any text data outside the code and
    # make sure that whatever non python lines included in python code is commented out 
    # and ensure the resultant code is executable format.
    # For example:
    # //
    # import pandas as pd
    # file_path = 'Dummy_Data.xlsx'
    # data_exc = pd.read_excel(file_path)
    # top_10_customers = data_exc.sort_values(by='TOTAL', ascending=False).head(10)
    # result = top_10_customers.to_dict(orient='records')
    # print(result)
    # //
    # The data is in an Excel file located at {file_path} and columns are {columns}.
    # Load the Excel file into a pandas DataFrame, and fetch the all columns and get related columns required for query from DataFrame and
    # perform the requested operation, and store the result in a variable called "result" always [/INST]"""
    quarters={
        "Quarter1(Q1)":"Apr_23,May_23,Jun_23",
        "Quarter2(Q2)":"Jul_23,Aug_23,Sep_23",
        "Quarter3(Q3)":"Oct_23,Nov_23,Dec_23",
        "Quarter4(Q4)":"Jan_23,Feb_23,Mar_23",
    }
    prompt = f"""[INST]
    You are an expert Python programmer. Write only Python code to perform the following task: {query}.
    Ensure the code starts with // and ends with // always.
    Do not include any explanations or additional text outside the code.
    
    **Ensure the code does not have indentation errors.**

    The data is in an Excel file located at '{file_path}' and the columns are {list(columns)} and quarters are {quarters}.
    Load the Excel file into a pandas DataFrame, and fetch the required columns to perform the requested operation.
    Store the result in a variable called "result" always.

    Example format (do not include this explanation in the output):
    //
    import pandas as pd
    file_path = {file_path}
    df = pd.read_excel(file_path)
    result = df.describe()  
    //

    Now, write the code for: {query}[/INST]
    """
    response = watsonx_llm.complete(prompt)
    print('typeof',type(response))
    code = response
    print(type(code))
    code=(str(code))
    print('actual code')
    print(code)
    # code = "\n".join([line.lstrip() for line in code.splitlines()])
    # code =code.split("//")[1].strip()
    try:
      code = code.split("//")[1].strip()
    except IndexError:
        return None
    code = textwrap.dedent(code)
    print('before splitted')
    print(code)
    lines = code.split('\n')

    # Strip the first line of leading spaces and dedent the rest
    if lines:
        first_line = lines[0].strip()
        remaining_lines = "\n".join(lines[1:])
        remaining_lines = textwrap.dedent(remaining_lines)
        code = f"{first_line}\n{remaining_lines}"
    
    print(type(code))
    print('splitted')
    print(code)
    return code

def execute_code(code, df):
    local_scope = {'df': df}
    try:
        exec(code, globals(), local_scope)
        return local_scope.get('result', None), None
    except Exception as e:
        return None, str(e)

def retry_execution(query, file_path, columns, df, max_retries=10):
    for attempt in range(max_retries):
        code = generate_code(query, file_path, columns)
        print(f"Generated Code Attempt {attempt+1}:\n")
        print(code)
        result, error = execute_code(code, df)
        if result is not None:
            return result
        else:
            print(f"Execution failed with error: {error}")
    return None

def desresponse(query, result):
    prompt = f"""[INST]
    I am getting result for the {query} from a data source. Now You need to format the {result} obtained in a tabular format and print the formatted result in plain text table and
    describe\summarize about the data inside the result obtained for the {query} in maximum 1 to 2 lines based length of content. 
    Avoid any HTML, XML, or other markup languages. Provide only plain text table.
    Note: Just print only plain text table and description of result as response without any other text.
    Example:
        Table:
        | Column1       | Column2   |
        |---------------|-----------|
        | Value1        | Value2    |
        
        Summary: This is a brief summary[/INST].
    """
    response = watsonx_llm.complete(prompt)
    return str(response)

@app.route('/codegenerate', methods=['POST'])
def codegenerate():
    data = request.get_json()
    query = data['message']
    # file_path = data['file_path']
    file_path = 'Dummy_data.xlsx'
    df = pd.read_excel(file_path)
    columns = df.columns
    result = retry_execution(query, file_path, columns, df)
    print("Final Result:", result)

    if result is not None:
        try:
            res = desresponse(query, result)
            return jsonify({'result': res}), 200
        except Exception as e:
            print(f"Desresponse failed with error: {e}")
            return jsonify({'result': str(result)}), 200
    else:
        return jsonify({'result': 'Failed to generate correct response after multiple attempts'}), 500


