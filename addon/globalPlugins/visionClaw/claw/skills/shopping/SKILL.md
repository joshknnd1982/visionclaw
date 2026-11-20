---
name: Shop online safely
description: Reads prices, totals and choices exactly, and leaves the buying to the user.
when: shop, shopping, buy, basket, cart, checkout, price, prices, order, product, delivery cost
uses: web_page, read_text, describe, click, page_outline, pick_option, pick_seat, look_picture
log: errors
lands: told
---

Read prices, totals, delivery costs, sizes and quantities exactly as written, with their currency. Say when a price or an offer is only in a picture. Never press a button that buys, orders, pays, subscribes or confirms: the user does that. Say when something is out of stock or when an extra item was added to the basket.
