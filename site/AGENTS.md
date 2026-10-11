## Frontend Development

- Always use the pointer (hand) cursor (`cursor-pointer`) on interactive elements like buttons
- This is the marketing site: every word is product copy. No placeholder text, and no generic marketing lines ("unlock your team's potential"). Read it out loud before shipping.
- Product visuals are rendered components (`src/components/landing/product-mocks.tsx`), not screenshots or stock art.
- Links into the product use `src/lib/links.ts` (`VITE_APP_URL`), and absolute URLs for Open Graph use `VITE_SITE_URL`.
- Check the page at phone width (390px): no horizontal scroll.
