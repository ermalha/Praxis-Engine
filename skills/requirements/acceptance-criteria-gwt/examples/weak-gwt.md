# Weak GWT Example

**Story:** As a user, I want to search for products.

## Scenario 1 (Weak): Search works
- **Given** the user is on the site
- **When** they search
- **Then** it works correctly

### Problems:
- "on the site" — where specifically?
- "they search" — search for what? How?
- "works correctly" — untestable, not observable

## Scenario 2 (Weak): Compound scenario
- **Given** the user is logged in
- **When** they type "shoes" and press Enter and click the first result and add to cart
- **Then** the cart icon shows 1 item and a success toast appears and the product page updates

### Problems:
- Multiple actions in When (search, click, add to cart = 3 scenarios)
- Multiple outcomes in Then (each should be its own check)
- Tests UI implementation ("toast appears")

## How to fix Scenario 2:

### Scenario 2a: Search returns results
- **Given** the product catalog contains 5 items matching "shoes"
- **When** the user searches for "shoes"
- **Then** 5 matching products are displayed

### Scenario 2b: User adds search result to cart
- **Given** the user is viewing search results
- **When** they add "Running Shoe Pro" to cart
- **Then** the cart count increases by 1
