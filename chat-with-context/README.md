<div align="center">

# 💬 Chat with context web component

[![NPM](https://img.shields.io/npm/v/@sib-swiss/chat-with-context)](https://www.npmjs.com/package/@sib-swiss/chat-with-context)

</div>

A web component to easily deploy an interface for a chat with context. It is the frontend for the chat API built at [github.com/sib-swiss/sparql-llm](https://github.com/sib-swiss/sparql-llm). It provides a user-friendly chat interface with additional features to inspect the context used by the LLM to generate the response.

👆️ You can **try it** for a few SPARQL endpoints of the [SIB](https://www.sib.swiss/), such as UniProt and Bgee, at **[chat.expasy.org](https://chat.expasy.org)**

## 🚀 Use

1. Import from a CDN:

   ```html
   <script type="module" src="https://unpkg.com/@sib-swiss/chat-with-context"></script>
   <link href="https://unpkg.com/@sib-swiss/chat-with-context/dist/chat-with-context.css" rel="stylesheet" />
   ```

   Or install with a package manager in your project:

   ```bash
   npm install --save @sib-swiss/chat-with-context
   # or
   pnpm add @sib-swiss/chat-with-context
   ```

   And import in your JS/TS file with:

   ```ts
   import "@sib-swiss/chat-with-context";
   import "@sib-swiss/chat-with-context/dist/chat-with-context.css";
   ```

2. Use the custom element in your HTML/JSX/TSX code:

   ```html
   <chat-with-context
     chat-endpoint="http://localhost:8000/chat"
     feedback-endpoint="http://localhost:8000/feedback"
     api-key="public_apikey_used_by_frontend_to_prevent_abuse_from_robots"
     examples="Which resources are available at the SIB?,How can I get the HGNC symbol for the protein P68871?,What are the rat orthologs of the human TP53?,Where is expressed the gene ACE2 in human?,Anatomical entities where the INS zebrafish gene is expressed and its gene GO annotations,List the genes in primates orthologous to genes expressed in the fruit fly eye"
   ></chat-with-context>
   ```

> [!WARNING]
>
> It uses TailwindCSS for styling

### 📝 Basic example

No need for a complex project you can integrate SPARQL editor in any HTML page by importing from a CDN!

Create a `index.html` file with:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SPARQL editor dev</title>
    <meta name="description" content="SPARQL editor demo page" />
    <link rel="icon" type="image/png" href="https://upload.wikimedia.org/wikipedia/commons/f/f3/Rdf_logo.svg" />
    <!-- Import the module from a CDN -->
    <script type="module" src="https://unpkg.com/@sib-swiss/chat-with-context"></script>
  </head>

  <body>
    <div>
      <chat-with-context
        chat-endpoint="http://localhost:8000/chat"
        feedback-endpoint="http://localhost:8000/feedback"
        api-key="public_apikey_used_by_frontend_to_prevent_abuse_from_robots"
        examples="Which resources are available at the SIB?,How can I get the HGNC symbol for the protein P68871?,What are the rat orthologs of the human TP53?,Where is expressed the gene ACE2 in human?,Anatomical entities where the INS zebrafish gene is expressed and its gene GO annotations,List the genes in primates orthologous to genes expressed in the fruit fly eye"
      ></chat-with-context>
    </div>
  </body>
</html>
```

Then just open this HTML page in your favorite browser.

You can also start a basic web server with NodeJS or Python:

```bash
npx http-server
# or
python -m http.server
```

# 🧑‍💻 Development

Install:

```sh
npm i
```

Start in dev:

```sh
npm run dev
```

Build package:

```sh
npm run build
```

Build demo website (used by the python API), running this will update the webapp served by the python API in `../src/sparql_llm/agent/webapp`:

```sh
npm run build:demo
```

Format and lint:

```sh
npm run fmt
npm run lint
```

Publish new version:

```sh
npm version patch
```
