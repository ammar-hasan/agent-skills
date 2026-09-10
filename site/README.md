# Agent Skills catalog

The public catalog lives at **https://ammar-hasan.github.io/agent-skills/** and is hosted on GitHub Pages.

The installable skills live in the repository’s `skills/` directory and do not depend on this website.

## Work locally

Use Node.js 22.13+ and npm:

```sh
npm ci
npm run dev
```

Open `/agent-skills/` on the local URL printed by the server. To build the static website:

```sh
npm run build
```

Next.js exports the site into `out/`. GitHub Pages serves only this directory; no server, account identifiers, environment files, or hosting credentials are needed. Browser source maps are disabled.

## Content and publishing

Catalog content lives in `catalog.json`. Adding a selected skill there creates its catalog entry and install command. Keep the root README in sync.

The Pages workflow validates the public content, builds the static site, and deploys it after a push to `main`. Pull requests run validation without deploying. Asset and home links use the `/agent-skills/` repository path.

`public/og.png` is the social preview card. It uses the catalog’s ivory and forest green palette, the headline “Good workflows. Shared as skills.”, and the public maintainer attribution.
