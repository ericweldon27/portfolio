"""SXO audit: compare websites on UX, SEO and AEO using only free data."""
import warnings

# macOS system Python ships LibreSSL; urllib3 warns about it on import.
warnings.filterwarnings("ignore", message=".*OpenSSL.*")
