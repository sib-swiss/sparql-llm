import os
import pandas as pd
"""
Error analysis after manual inspection of the results
"""

csv_file = os.path.join('data', 'benchmarks', '20250624_1346_Text2SPARQL_Error_Analysis.csv')
print('Error Histogram', pd.read_csv(csv_file)['comment'].str.split('/').explode().str.strip().value_counts())