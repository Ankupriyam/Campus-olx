# Campus OLX - Campus-Exclusive Marketplace

Campus OLX is a secure, localized, campus-exclusive marketplace platform designed for university students to buy and sell used items (like cycle, books, laptops) safely. By limiting access strictly to the campus community, it builds a trusted trading environment, supports student finances, and promotes a sustainable circular economy.

---

##  Key Features

* **Glassmorphic Single Page Application (SPA):** Built using Vanilla HTML, CSS, and JS with a premium neon dark theme and smooth micro-animations.
* **Dual-Dropdown Usage Tracking:** Allows sellers to specify the exact age of their items using separate dropdowns for **Years (0 to 5)** and **Months (0 to 12)**.
* **Granular Role-Based Access:** 
  * **Buyers** can search listings, filter by category/price, and reveal seller contact details (if logged in).
  * **Sellers** can manage listings, upload up to 5 images, mark items as sold, and access seller-specific metrics.
* **Personalized Seller Analytics:** A dedicated dashboard showing sales metrics, standard deviation of prices, and percentiles calculated over the seller's inventory.
* **Headless Data Visualization:** Serves dynamically generated charts (Category Prices, Inventory status, Listing trends) rendered in memory on the backend.
* **Robust Fallback Auth:** Integrates standard session cookies with a custom `X-User-Id` request header fallback to bypass cookie blocking on local browser environments (e.g. running from `file://` protocols).

---

## System Architecture

### 1. Frontend (Client-Side)
* **HTML5 & CSS3:** Responsive UI using CSS Grid and Flexbox with zero CSS frameworks, relying on a unified CSS custom property design system.
* **Vanilla JavaScript:** Performs DOM updates dynamically (e.g., rendering cards via `renderGrid()`), sanitizes inputs, handles client state (`localStorage`), and packages uploads using `FormData` and `fetch()`.

### 2. Backend (Flask API Server)
* **Routing & Controllers:** Flask routes handle item fetching, creation, deletion, status toggling, and user authentication.
* **Security & Sanitization:** 
  * Passwords hashed using **SHA-256 (`hashlib`)**.
  * File uploads sanitized using **`werkzeug.utils.secure_filename`** to prevent directory traversal.
  * Role enforcement decorators (`@seller_required` and `@login_required`).

### 3. Database & Storage Layer
* **NoSQL JSON Storage:** Uses lightweight local file systems (`listings.json` and `users.json`).
* **Pandas Integration:** Writes to the database are performed by reading lists into Pandas DataFrames and calling `df.to_json(orient='records')` to guarantee strict schema formatting.
* **UUID Generation:** Generates Universally Unique Identifiers (`uuid.uuid4`) for listings and user ids to prevent data collisions.

### 4. Data Science & Analytics Engine
* **Pandas:** Cleans data, groups active listings by category (`groupby`), and filters analytics data.
* **NumPy:** Performs mathematical statistics on prices, calculating the standard deviation (`np.std`) and 25th/75th percentiles (`np.percentile`).
* **Matplotlib:** Configured to run in headless mode (`matplotlib.use('Agg')`). It draws bar charts, line trends, and donut charts, saving them directly to the `uploads/` directory with unique `seller_id` suffixes to support concurrent sellers without collisions.

---

##  Tech Stack Summary

| Tool/Library | Purpose |
| :--- | :--- |
| **Flask** | Backend micro-framework & API Server |
| **Pandas** | DB Serialization & Data aggregation |
| **NumPy** | Statistical analytics (averages, std deviation, percentiles) |
| **Matplotlib** | Headless server-side chart image rendering |
| **UUID** | Alphanumeric unique key generation |
| **Hashlib** | Password security (SHA-256 Hashing) |
| **Werkzeug** | Secure upload file-name sanitization |
| **Vanilla JS / HTML / CSS** | Client-side presentation & interactive logic |

---

##  Running Locally

1. **Prerequisites:**
   * Python 3.10+
   * Pip packages: `pip install Flask flask-cors pandas numpy matplotlib`

2. **Start the Flask server:**
   ```bash
   python server.py
   ```
   *The server runs at `http://localhost:3001`.*
