from quart import request

async def apply_security_headers(response):
    """
    Applies strict HTTP security headers to all outbound Quart responses.
    Fixes OWASP ZAP Baseline DAST Warnings [10020, 10021, 10038, 10063, 90004].
    """
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://unpkg.com https://www.youtube.com https://s.ytimg.com; frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com; style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https: https://i.ytimg.com; report-uri /api/security/csp-report;"
    
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    if 'Server' in response.headers:
        del response.headers['Server']
        
    return response

def init_security_headers(app):
    """Registers the middleware with the main Quart application."""
    app.after_request(apply_security_headers)
