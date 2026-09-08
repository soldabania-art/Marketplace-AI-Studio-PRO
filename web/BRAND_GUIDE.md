# TROVENDI brand guide

## Identity

- Product name: **TROVENDI** (always uppercase in brand lockups and public product references).
- Primary domain: **trovendi.ru**.
- Descriptor: **AI Commerce OS**.
- Core promise: from one product photo to a marketplace-ready launch and ongoing AI-assisted store management.

## Mark

The mark combines a capital **T** with an upward arrow. It represents a product entering the market, controlled growth and one clear management direction. The source SVG files are `app/icon.svg` and `public/trovendi-mark.svg`; React interfaces use `components/BrandLogo.js`.

## Color system

| Role | Color |
| --- | --- |
| Base | `#0B1728` |
| Growth green | `#42E7A4` |
| Intelligence blue | `#5BA8FF` |
| AI purple | `#9F7AEA` |

## Product and migration rules

- Customer-facing copy must use TROVENDI; the previous public name is retired.
- Existing technical slugs, cookie names, local-storage keys, database names and service IDs stay unchanged until a tested migration exists.
- `trovendi.ru` becomes canonical after DNS and Vercel domain verification; the existing Vercel URL remains a technical fallback.
- The same mark, name and notification identity are used by the website, installable PWA and future Android application.
