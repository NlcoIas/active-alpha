"""Test configuration and fixtures."""

import os

# Set test environment before importing app modules
os.environ["ENVIRONMENT"] = "test"
os.environ["FMP_API_KEY"] = "test_key"
os.environ["ADMIN_API_KEY"] = "test_admin_key"
