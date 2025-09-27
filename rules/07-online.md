## **Mission Briefing: Online Behavior**

-  **Directive:**

-  **Requirements:**
    1. **Browse sites with human-like behavior:** Implement code to access websites with behavior that mimics human browsing activity. Implement headers to send requests to websites that are as complete as a human user browsing the website would send. Parse received requests from websites for CAPTCHA activity. Do not spam the website repeatedly if there are errors. Read the site source to determine if a code solution is possible to defeat the anti-bot detection by using mouse movements and clicks, typing characters into boxes if required, and waiting until the checkbox appears and clicking it if possible. If unable to overcome the CAPTCHA in two tries, implement a wait until a manual CAPTCHA can be completed and notify the user.
    2. **Determine subdomains that may disallow robots:** For any online source to be accessed, prior to accessing the source, navigate to the source site's robots.txt to understand which subdomains may experience errors if the site believes a robot is accessing it.
    3. **Try to locate understand the site's Terms of Service:** As best as possible without spending more than a minute on the first visit to a site, locate the Terms of Service. Implement code that honors the Terms of Service as a human would.
    4. **Determine applicable rate limits:** Find out the applicable rate limits to comply with the Terms of Service for the site. Create code that respects the rate limits.
    5. **Document all sources used:** Create documentation for all sources used, indicating what information was retrieved from what sources, and how that data can be found.