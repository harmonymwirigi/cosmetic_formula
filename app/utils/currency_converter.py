# backend/app/utils/currency_converter.py

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ..models import Currency
from ..config import settings
import logging

logger = logging.getLogger(__name__)

class CurrencyConverter:
    """
    Currency conversion utility with caching and external API integration
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.cache_duration = timedelta(hours=24)  # Cache exchange rates for 24 hours
        
    async def get_exchange_rate(self, from_currency: str, to_currency: str = "USD") -> float:
        """
        Get exchange rate from one currency to another
        
        Args:
            from_currency: Source currency code (e.g., 'EUR')
            to_currency: Target currency code (default: 'USD')
            
        Returns:
            Exchange rate as float
        """
        if from_currency == to_currency:
            return 1.0
            
        # Try to get from database cache first
        cached_rate = self._get_cached_rate(from_currency, to_currency)
        if cached_rate:
            return cached_rate
            
        # Fetch from external API if not cached or expired
        try:
            rate = await self._fetch_exchange_rate_from_api(from_currency, to_currency)
            self._cache_exchange_rate(from_currency, to_currency, rate)
            return rate
        except Exception as e:
            logger.error(f"Failed to fetch exchange rate for {from_currency} to {to_currency}: {e}")
            # Fall back to cached rate even if expired
            fallback_rate = self._get_cached_rate(from_currency, to_currency, ignore_expiry=True)
            if fallback_rate:
                logger.warning(f"Using expired exchange rate for {from_currency} to {to_currency}")
                return fallback_rate
            else:
                logger.error(f"No exchange rate available for {from_currency} to {to_currency}")
                return 1.0  # Default fallback
    
    def _get_cached_rate(self, from_currency: str, to_currency: str, ignore_expiry: bool = False) -> Optional[float]:
        """Get cached exchange rate from database"""
        try:
            # Get the most recent rate for the from_currency
            currency = self.db.query(Currency).filter(
                Currency.code == from_currency.upper(),
                Currency.is_active == True
            ).first()
            
            if not currency:
                return None
                
            # Check if rate is fresh enough
            if not ignore_expiry:
                if currency.last_updated < datetime.utcnow() - self.cache_duration:
                    return None
            
            # Convert from USD rate to target currency
            if to_currency.upper() == "USD":
                return currency.exchange_rate_to_usd
            else:
                # Get target currency rate
                target_currency = self.db.query(Currency).filter(
                    Currency.code == to_currency.upper(),
                    Currency.is_active == True
                ).first()
                
                if not target_currency:
                    return None
                    
                # Convert: from_currency -> USD -> to_currency
                return currency.exchange_rate_to_usd / target_currency.exchange_rate_to_usd
                
        except Exception as e:
            logger.error(f"Error getting cached exchange rate: {e}")
            return None
    
    async def _fetch_exchange_rate_from_api(self, from_currency: str, to_currency: str) -> float:
        """
        Fetch exchange rate from external API
        Using exchangerate-api.io as an example (free tier available)
        """
        api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', None)
        
        if not api_key:
            # Use free tier without API key (limited requests)
            url = f"https://api.exchangerate-api.io/v4/latest/{from_currency.upper()}"
        else:
            url = f"https://v6.exchangerate-api.io/v6/{api_key}/latest/{from_currency.upper()}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('result') == 'success':
                        rates = data.get('conversion_rates', {})
                        rate = rates.get(to_currency.upper())
                        
                        if rate:
                            return float(rate)
                        else:
                            raise ValueError(f"Rate for {to_currency} not found in API response")
                    else:
                        raise ValueError(f"API returned error: {data.get('error-type', 'Unknown error')}")
                else:
                    raise ValueError(f"API request failed with status {response.status}")
    
    def _cache_exchange_rate(self, from_currency: str, to_currency: str, rate: float):
        """Cache exchange rate in database"""
        try:
            # Store rate as conversion to USD for consistency
            if to_currency.upper() != "USD":
                # We need to store the USD rate, so convert the rate accordingly
                # This is a simplified approach - in production you might want to fetch USD rates directly
                pass
            
            # Update or create currency record
            currency = self.db.query(Currency).filter(
                Currency.code == from_currency.upper()
            ).first()
            
            if currency:
                if to_currency.upper() == "USD":
                    currency.exchange_rate_to_usd = rate
                currency.last_updated = datetime.utcnow()
            else:
                # Create new currency record
                if to_currency.upper() == "USD":
                    currency = Currency(
                        code=from_currency.upper(),
                        name=self._get_currency_name(from_currency),
                        symbol=self._get_currency_symbol(from_currency),
                        exchange_rate_to_usd=rate,
                        is_active=True
                    )
                    self.db.add(currency)
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error caching exchange rate: {e}")
            self.db.rollback()
    
    def _get_currency_name(self, currency_code: str) -> str:
        """Get currency name from code"""
        currency_names = {
            'USD': 'US Dollar',
            'EUR': 'Euro',
            'GBP': 'British Pound',
            'CAD': 'Canadian Dollar',
            'AUD': 'Australian Dollar',
            'JPY': 'Japanese Yen',
            'CHF': 'Swiss Franc',
            'CNY': 'Chinese Yuan',
            'INR': 'Indian Rupee',
            'BRL': 'Brazilian Real',
            'MXN': 'Mexican Peso',
            'ZAR': 'South African Rand',
            'SEK': 'Swedish Krona',
            'NOK': 'Norwegian Krone',
            'DKK': 'Danish Krone',
            'PLN': 'Polish Zloty',
            'CZK': 'Czech Koruna',
            'HUF': 'Hungarian Forint',
            'RUB': 'Russian Ruble',
            'TRY': 'Turkish Lira',
            'KRW': 'South Korean Won',
            'SGD': 'Singapore Dollar',
            'HKD': 'Hong Kong Dollar',
            'NZD': 'New Zealand Dollar',
            'THB': 'Thai Baht',
            'MYR': 'Malaysian Ringgit',
            'PHP': 'Philippine Peso',
            'IDR': 'Indonesian Rupiah',
            'VND': 'Vietnamese Dong',
        }
        return currency_names.get(currency_code.upper(), f"{currency_code.upper()} Currency")
    
    def _get_currency_symbol(self, currency_code: str) -> str:
        """Get currency symbol from code"""
        currency_symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'CAD': 'C$',
            'AUD': 'A$',
            'JPY': '¥',
            'CHF': 'CHF',
            'CNY': '¥',
            'INR': '₹',
            'BRL': 'R$',
            'MXN': '$',
            'ZAR': 'R',
            'SEK': 'kr',
            'NOK': 'kr',
            'DKK': 'kr',
            'PLN': 'zł',
            'CZK': 'Kč',
            'HUF': 'Ft',
            'RUB': '₽',
            'TRY': '₺',
            'KRW': '₩',
            'SGD': 'S$',
            'HKD': 'HK$',
            'NZD': 'NZ$',
            'THB': '฿',
            'MYR': 'RM',
            'PHP': '₱',
            'IDR': 'Rp',
            'VND': '₫',
        }
        return currency_symbols.get(currency_code.upper(), currency_code.upper())
    
    async def convert_amount(self, amount: float, from_currency: str, to_currency: str = "USD") -> float:
        """
        Convert an amount from one currency to another
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code (default: USD)
            
        Returns:
            Converted amount
        """
        if amount == 0:
            return 0.0
            
        rate = await self.get_exchange_rate(from_currency, to_currency)
        return amount * rate

    def get_supported_currencies(self) -> Dict[str, str]:
        """Get list of supported currencies"""
        currencies = self.db.query(Currency).filter(Currency.is_active == True).all()
        return {currency.code: f"{currency.symbol} {currency.name}" for currency in currencies}
    
    def initialize_default_currencies(self):
        """Initialize database with common currencies"""
        default_currencies = [
            {'code': 'USD', 'name': 'US Dollar', 'symbol': '$', 'rate': 1.0},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'rate': 0.85},
            {'code': 'GBP', 'name': 'British Pound', 'symbol': '£', 'rate': 0.73},
            {'code': 'CAD', 'name': 'Canadian Dollar', 'symbol': 'C$', 'rate': 1.35},
            {'code': 'AUD', 'name': 'Australian Dollar', 'symbol': 'A$', 'rate': 1.55},
            {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥', 'rate': 150.0},
        ]
        
        for curr_data in default_currencies:
            existing = self.db.query(Currency).filter(Currency.code == curr_data['code']).first()
            if not existing:
                currency = Currency(
                    code=curr_data['code'],
                    name=curr_data['name'],
                    symbol=curr_data['symbol'],
                    exchange_rate_to_usd=curr_data['rate'],
                    is_active=True
                )
                self.db.add(currency)
        
        self.db.commit()