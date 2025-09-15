#!/usr/bin/env python3
"""
Generate a comprehensive test report for dashboard functionality.
"""

import json
import os
from datetime import datetime
from pathlib import Path

def load_test_results():
    """Load test results from JSON files."""
    results_dir = Path("tests")
    test_files = list(results_dir.glob("dashboard_*_results_*.json"))
    
    if not test_files:
        return None
    
    # Get the most recent results
    latest_file = max(test_files, key=os.path.getctime)
    
    with open(latest_file, 'r') as f:
        return json.load(f)

def generate_html_report(results):
    """Generate an HTML test report."""
    if not results:
        return "<h1>No test results found</h1>"
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Test Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #007bff;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #007bff;
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            color: #333;
        }}
        .summary-card .number {{
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }}
        .test-results {{
            margin-top: 30px;
        }}
        .test-item {{
            background: #f8f9fa;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 4px solid #28a745;
        }}
        .test-item.failed {{
            border-left-color: #dc3545;
        }}
        .test-item h4 {{
            margin: 0 0 10px 0;
            color: #333;
        }}
        .test-details {{
            font-size: 0.9em;
            color: #666;
        }}
        .performance-metrics {{
            margin-top: 30px;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 10px;
            background: #f8f9fa;
            margin: 5px 0;
            border-radius: 5px;
        }}
        .metric-name {{
            font-weight: bold;
        }}
        .metric-value {{
            color: #007bff;
        }}
        .status-pass {{
            color: #28a745;
            font-weight: bold;
        }}
        .status-fail {{
            color: #dc3545;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Dashboard Test Report</h1>
            <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Total Tests</h3>
                <div class="number">{results.get('total_tests', 0)}</div>
            </div>
            <div class="summary-card">
                <h3>Passed</h3>
                <div class="number status-pass">{results.get('passed_tests', 0)}</div>
            </div>
            <div class="summary-card">
                <h3>Failed</h3>
                <div class="number status-fail">{results.get('failed_tests', 0)}</div>
            </div>
            <div class="summary-card">
                <h3>Success Rate</h3>
                <div class="number">{results.get('success_rate', 0):.1f}%</div>
            </div>
        </div>
        
        <div class="test-results">
            <h2>Test Results</h2>
"""
    
    # Add test results
    for result in results.get('results', []):
        status_class = 'failed' if not result.get('success', False) else ''
        status_text = 'PASS' if result.get('success', False) else 'FAIL'
        status_class_name = 'status-pass' if result.get('success', False) else 'status-fail'
        
        html += f"""
            <div class="test-item {status_class}">
                <h4><span class="{status_class_name}">{status_text}</span> {result.get('file', 'Unknown')}</h4>
                <div class="test-details">
                    Return Code: {result.get('return_code', 'N/A')}<br>
                    {f"Error: {result.get('stderr', '')}" if result.get('stderr') else ''}
                </div>
            </div>
        """
    
    # Add performance metrics if available
    if 'performance' in results:
        html += """
        <div class="performance-metrics">
            <h2>Performance Metrics</h2>
        """
        
        for metric, value in results['performance'].items():
            html += f"""
            <div class="metric">
                <span class="metric-name">{metric}</span>
                <span class="metric-value">{value}</span>
            </div>
            """
        
        html += "</div>"
    
    html += """
        </div>
    </div>
</body>
</html>
"""
    
    return html

def main():
    """Generate test report."""
    print("Generating Dashboard Test Report...")
    
    # Load test results
    results = load_test_results()
    
    if not results:
        print("No test results found. Please run tests first.")
        return 1
    
    # Generate HTML report
    html_content = generate_html_report(results)
    
    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"tests/dashboard_test_report_{timestamp}.html"
    
    with open(report_file, 'w') as f:
        f.write(html_content)
    
    print(f"Test report generated: {report_file}")
    print(f"Open the file in a web browser to view the report.")
    
    return 0

if __name__ == "__main__":
    exit(main())

