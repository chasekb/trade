# Security Tests

This document describes the security tests for the Trading Bot system.

## Overview

The security test suite (`test_security.py`) provides comprehensive coverage of security-critical functionality including:

1. **Input Validation** - Tests for proper validation of API inputs
2. **SQL Injection Prevention** - Tests for SQL injection vulnerabilities
3. **Path Traversal Prevention** - Tests for path traversal vulnerabilities
4. **Rate Limiting** - Tests for rate limiting enforcement
5. **Authentication/Authorization** - Tests for authentication and authorization
6. **Data Sanitization** - Tests for XSS and injection prevention
7. **Error Handling** - Tests that errors don't leak sensitive information

## Running Security Tests

### Run All Security Tests

```bash
pytest tests/test_security.py -v
```

### Run Specific Test Classes

```bash
# Input validation tests
pytest tests/test_security.py::TestInputValidation -v

# SQL injection prevention tests
pytest tests/test_security.py::TestSQLInjectionPrevention -v

# Path traversal prevention tests
pytest tests/test_security.py::TestPathTraversalPrevention -v

# Rate limiting tests
pytest tests/test_security.py::TestRateLimiting -v

# Authentication tests
pytest tests/test_security.py::TestAuthenticationAuthorization -v

# Data sanitization tests
pytest tests/test_security.py::TestDataSanitization -v

# Error handling tests
pytest tests/test_security.py::TestErrorHandling -v
```

## Test Categories

### 1. Input Validation Tests

**Purpose:** Ensure all API endpoints properly validate input data.

**Tests:**
- Invalid strategy names
- Invalid date formats
- Invalid date ranges (start > end)
- Extreme parameter values
- Special characters in symbols
- Negative pagination values
- Extremely large pagination values
- Invalid trading parameters
- Path traversal in product IDs

**Expected Behavior:**
- Invalid inputs should return 400/422 status codes
- Extreme values should be bounded or rejected
- Special characters should be sanitized or rejected
- No crashes or unhandled exceptions

### 2. SQL Injection Prevention Tests

**Purpose:** Verify that the application is not vulnerable to SQL injection attacks.

**Tests:**
- SQL injection in product IDs
- SQL injection in cache keys
- Parameterized query verification

**Attack Vectors Tested:**
```sql
BTC-USD'; DROP TABLE candles; --
BTC-USD' OR '1'='1
BTC-USD'; DELETE FROM candles WHERE '1'='1
BTC-USD' UNION SELECT * FROM sqlite_master --
```

**Expected Behavior:**
- All queries use parameterized statements
- Malicious input does not execute SQL
- Application handles malicious input gracefully
- No database tables are dropped or modified

### 3. Path Traversal Prevention Tests

**Purpose:** Ensure file paths cannot be manipulated to access unauthorized files.

**Tests:**
- Database path validation
- Path normalization
- Relative path handling

**Attack Vectors Tested:**
```
../../../etc/passwd
..\\..\\..\\windows\\system32\\config\\sam
/etc/passwd
data/databases/../../secrets.txt
```

**Expected Behavior:**
- Paths are validated and normalized
- Access outside allowed directories is prevented
- Dangerous paths raise exceptions or are sanitized

### 4. Rate Limiting Tests

**Purpose:** Verify that rate limiting prevents abuse.

**Tests:**
- Rapid request handling
- Rate limit header presence
- Enforcement of limits

**Expected Behavior:**
- Excessive requests are rate limited (429 status)
- Rate limit information is available
- Legitimate requests are not blocked

### 5. Authentication/Authorization Tests

**Purpose:** Ensure sensitive operations require proper authentication.

**Tests:**
- Sensitive endpoint existence
- Credential exposure prevention
- Authorization checks

**Expected Behavior:**
- Sensitive endpoints exist and respond
- Credentials are never exposed in responses
- Unauthorized access is prevented

### 6. Data Sanitization Tests

**Purpose:** Prevent XSS and injection attacks through data sanitization.

**Tests:**
- XSS payload handling
- JSON injection prevention
- Output encoding

**Attack Vectors Tested:**
```html
<script>alert('xss')</script>
<img src=x onerror=alert('xss')>
javascript:alert('xss')
```

**Expected Behavior:**
- HTML tags are escaped or removed
- JavaScript code is not executed
- User input is properly sanitized before output

### 7. Error Handling Tests

**Purpose:** Ensure error messages don't leak sensitive information.

**Tests:**
- Stack trace exposure
- Internal path disclosure
- Exception detail leakage

**Expected Behavior:**
- Generic error messages in production
- No stack traces exposed to users
- No internal file paths or code disclosed

## Security Best Practices

### For Developers

1. **Always validate input** - Never trust user input
2. **Use parameterized queries** - Prevent SQL injection
3. **Sanitize output** - Prevent XSS attacks
4. **Validate file paths** - Prevent path traversal
5. **Implement rate limiting** - Prevent abuse
6. **Use authentication** - Protect sensitive operations
7. **Handle errors gracefully** - Don't leak information
8. **Keep dependencies updated** - Patch vulnerabilities
9. **Use HTTPS** - Encrypt data in transit
10. **Log security events** - Monitor for attacks

### Input Validation Guidelines

```python
# Good: Validate and bound inputs
def validate_pagination(page: int, page_size: int):
    page = max(1, min(page, 1000))
    page_size = max(1, min(page_size, 100))
    return page, page_size

# Good: Use Pydantic models
from pydantic import BaseModel, validator

class BacktestRequest(BaseModel):
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    
    @validator('strategy')
    def validate_strategy(cls, v):
        allowed = ['sma', 'rsi', 'macd', 'bollinger']
        if v not in allowed:
            raise ValueError(f'Invalid strategy: {v}')
        return v
```

### SQL Injection Prevention

```python
# Good: Use parameterized queries
cursor.execute(
    "SELECT * FROM candles WHERE product_id = ?",
    (product_id,)
)

# Bad: String concatenation
cursor.execute(
    f"SELECT * FROM candles WHERE product_id = '{product_id}'"
)
```

### Path Traversal Prevention

```python
# Good: Validate paths
from pathlib import Path

def validate_db_path(db_path: str) -> Path:
    base = Path("data/databases").resolve()
    target = Path(db_path).resolve()
    
    # Ensure target is within base directory
    try:
        target.relative_to(base)
        return target
    except ValueError:
        raise ValueError("Invalid database path")
```

## Known Limitations

1. **Rate Limiting** - Currently implemented per-hour, could be enhanced with IP-based limiting
2. **Authentication** - No authentication currently implemented for API endpoints
3. **Session Management** - Sessions use timestamp-based IDs (predictable)
4. **CORS** - No CORS configuration visible
5. **Input Validation** - Some endpoints may lack comprehensive validation

## Recommendations

### High Priority
1. Implement authentication for sensitive endpoints
2. Add comprehensive input validation to all endpoints
3. Enhance rate limiting with IP-based tracking
4. Implement secure session management

### Medium Priority
1. Add CORS configuration
2. Implement request signing
3. Add audit logging for sensitive operations
4. Set up automated security scanning

### Low Priority
1. Add penetration testing
2. Implement OAuth2/JWT authentication
3. Add security headers (CSP, HSTS, etc.)
4. Conduct security code review

## Continuous Security

### Pre-commit Checks
```bash
# Run security tests before committing
pytest tests/test_security.py -v
```

### CI/CD Integration
```yaml
# Add to CI/CD pipeline
- name: Security Tests
  run: pytest tests/test_security.py --cov=src/trade_bot --cov-report=html
```

### Dependency Scanning
```bash
# Check for vulnerable dependencies
pip install pip-audit
pip-audit

# Or use safety
pip install safety
safety check
```

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do not** open a public issue
2. Email the security team (if applicable)
3. Provide detailed information about the vulnerability
4. Include steps to reproduce
5. Suggest a fix if possible

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

---

**Last Updated:** October 15, 2025  
**Version:** 1.0.0

