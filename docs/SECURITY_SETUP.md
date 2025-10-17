# Security Setup Guide

## Credential Management

This project requires Coinbase API credentials for trading functionality. For security reasons, credentials should never be committed to version control.

### Setting Up Credentials

1. **Create a `.env` file** in the project root:
   ```bash
   cp docs/env.example .env
   ```

2. **Get your Coinbase API credentials**:
   - Visit [Coinbase Pro API Settings](https://pro.coinbase.com/profile/api)
   - Create a new API key with appropriate permissions
   - Copy the API key, secret, and passphrase

3. **Update your `.env` file** with your actual credentials:
   ```bash
   COINBASE_API_KEY=your_actual_32_character_key
   COINBASE_API_SECRET=your_actual_88_character_secret
   COINBASE_PASSPHRASE=your_actual_passphrase
   ```

4. **Verify your setup**:
   ```bash
   python -c "from src.trade_bot.core.config import TradingConfig; TradingConfig.from_env().validate(); print('Credentials validated successfully!')"
   ```

### Security Best Practices

- **Never commit `.env` files** - they are already in `.gitignore`
- **Rotate credentials regularly** - especially if they were ever exposed
- **Use environment-specific files** for different deployments
- **Monitor API usage** through Coinbase Pro dashboard
- **Use minimal required permissions** for API keys

### If Credentials Were Exposed

If your credentials were ever committed to version control:

1. **Immediately rotate your API keys** in Coinbase Pro
2. **Update your `.env` file** with new credentials
3. **Consider using a secrets management service** for production deployments

### Environment Variables Reference

See `docs/env.example` for a complete list of available environment variables and their descriptions.
