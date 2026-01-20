# 🪵 Changelog

## [0.1.3](https://github.com/sib-swiss/sparql-llm/compare/v0.1.2..v0.1.3) - 2026-01-20

### ⚙️ Continuous Integration

- Improve the compose setup to enable deploying dev with a simple `docker compose up` and prod with `podman compose -f compose.prod.yml up` - ([e4c74fa](https://github.com/sib-swiss/sparql-llm/commit/e4c74fa7f3a18f9158f7a5e48ff5607f1c133078))
- Remove py 3.10, add 3.14 from test workflow - ([b7cbf77](https://github.com/sib-swiss/sparql-llm/commit/b7cbf77cfb7ac550b6ed2678ca5fb503a80bc701))

### ⛰️ Features

- Improve UI for large messages and update icon for sending messages, fixes https://github.com/sib-swiss/sparql-llm/issues/7 - ([a03347c](https://github.com/sib-swiss/sparql-llm/commit/a03347c1b896b0bea0b5cf58239e37755a711c1a))
- Add loading spark around the stop button when loading a response - ([21ca03a](https://github.com/sib-swiss/sparql-llm/commit/21ca03ad941508d924e52caf014525c4e5248a35))
- Use FastAPI instead of Starlette for defining the API - ([53a7295](https://github.com/sib-swiss/sparql-llm/commit/53a7295f0667ec0bf07f3aa04b64c7427b077167))

### 🐛 Bug Fixes

- Fix base `Dockerfile` - ([f178f49](https://github.com/sib-swiss/sparql-llm/commit/f178f4911f6144167752cffbfdf5b6d58e4fe4b8))
- Fix issues related to types, update default model to use openrouter - ([f54eea7](https://github.com/sib-swiss/sparql-llm/commit/f54eea7ab260235bbf0e7c528383ad6314d0457a))
- Fix the SPARQL query to get examples - ([3303324](https://github.com/sib-swiss/sparql-llm/commit/3303324678a9943ac76a2ecdac46a203b1e6bf27))

### 🚜 Refactor

- Directly use qdrant_client instead of langchain vectorstore wrapper - ([4ace320](https://github.com/sib-swiss/sparql-llm/commit/4ace32042b457af9bd525026f73df76cdf3e15d6))

### 🛠️ Miscellaneous Tasks

- Update version in `mcp.json` - ([3c6ae77](https://github.com/sib-swiss/sparql-llm/commit/3c6ae77398d984e8d300d6d38e0a13a69c565a34))
- Update `server.json` MCP config - ([9dc8c5a](https://github.com/sib-swiss/sparql-llm/commit/9dc8c5a37d5040520a496b42750d88ef2caa64cb))
- Bump npm pkg to v0.0.18 - ([1cf9bf3](https://github.com/sib-swiss/sparql-llm/commit/1cf9bf30a4bd6c757e93147187834f31a3504244))
- Upgrade langchain dependencies to v1+, and update the compiled webapp - ([fbec7fa](https://github.com/sib-swiss/sparql-llm/commit/fbec7faf47fdb78fb21d89acb5e503496aa30491))
- Add sibils endpoint to list of endpoints - ([6caa847](https://github.com/sib-swiss/sparql-llm/commit/6caa8470307bb282abeff29b28113ab46467e3cd))
- Fix send question buttons alignment on chrome and safari - ([0172917](https://github.com/sib-swiss/sparql-llm/commit/01729179ab6b69b2cbca8c004be2ae67d7b94bfa))
- Fmt js component - ([1bc016b](https://github.com/sib-swiss/sparql-llm/commit/1bc016b1d03b7467f1d1753f99afe80a81fd72f8))
- Bump npm package to v0.0.19 - ([1ecb333](https://github.com/sib-swiss/sparql-llm/commit/1ecb333bbb251863cd27f8a7c2a691f722196ab1))
- Upgrade langchain dependencies - ([36d48ff](https://github.com/sib-swiss/sparql-llm/commit/36d48fffb73c827fdd481263997d40c0a82e052c))
- Fix indexing in prod when using multiple worker - ([586e54d](https://github.com/sib-swiss/sparql-llm/commit/586e54dc24d1fb54811a0d1a884846bb3651ff5e))

### 🧪 Testing

- Add benchmark script for biodata endpoints - ([4ae9765](https://github.com/sib-swiss/sparql-llm/commit/4ae97656f67cb0f9dd0c79563819a0f1af0a65e6))

## [0.1.2](https://github.com/sib-swiss/sparql-llm/compare/v0.1.1..v0.1.2) - 2025-10-14

### ⚙️ Continuous Integration

- Update actions versions - ([8a9b2c5](https://github.com/sib-swiss/sparql-llm/commit/8a9b2c58aebc5742327cfddd8ed457c718f7837b))

### ⛰️ Features

- Feat: use stdio by default when starting MCP server alone
feat: enable to provide settings such as endpoints list through a custom JSON file when starting MCP server - ([ce1649e](https://github.com/sib-swiss/sparql-llm/commit/ce1649ebd28e4c38ecb106e7e493277b5ee80c35))

### 🛠️ Miscellaneous Tasks

- Add config for https://github.com/modelcontextprotocol/registry/ - ([967d21c](https://github.com/sib-swiss/sparql-llm/commit/967d21cb1e4415b1a25aadc507e8b3f8ef08bc9b))

## [0.1.1](https://github.com/sib-swiss/sparql-llm/compare/v0.1.0..v0.1.1) - 2025-10-07

### ⚙️ Continuous Integration

- Add release.sh script and improve docs - ([ce4aa58](https://github.com/sib-swiss/sparql-llm/commit/ce4aa58e486c9ddbf92f8c450787972ff42a97ed))

### ⛰️ Features

- Use stdio by default when starting MCP server alone - ([12754c8](https://github.com/sib-swiss/sparql-llm/commit/12754c8b578692df86cce2d938515cda33433519))

### 🛠️ Miscellaneous Tasks

- Fix dependency issue - ([ef5ea39](https://github.com/sib-swiss/sparql-llm/commit/ef5ea398e642aec68b18213d4c37f7a0c98b05df))

## [0.1.0](https://github.com/sib-swiss/sparql-llm/tree/v0.1.0) - 2025-10-06

### ⚙️ Continuous Integration

- Improve test and release workflow, add pre-commit, and fmt for 3.10 - ([b124ee2](https://github.com/sib-swiss/sparql-llm/commit/b124ee284b2cea6979387868c3c1dd3197eeb3e9))

### ⛰️ Features

- Improve MCP integration, still need to fix how its called from the main expasy-agent - ([7b62fd1](https://github.com/sib-swiss/sparql-llm/commit/7b62fd178c9f5b02f77ceed205985b797b828fc9))
- Deploy mcp server on the chat API /mcp path. Migrate the whole app definition from fastapi to starlette - ([6754413](https://github.com/sib-swiss/sparql-llm/commit/67544138e2c2b60e7039ef4c95e6b3bd1e79eb85))
- Init vectordb on startup if not yet initialized, add force_index setting - ([a7347fc](https://github.com/sib-swiss/sparql-llm/commit/a7347fc756e1919f090c65e8c94d4e8b9144ec26))
- Store endpoints metadata as JSON file to avoid having to query the endpoints everytime, improve logger setup - ([f59753b](https://github.com/sib-swiss/sparql-llm/commit/f59753b56f72019753482bc79f8c90631b8498a2))

### 🐛 Bug Fixes

- Fix deployment - ([38c65f9](https://github.com/sib-swiss/sparql-llm/commit/38c65f9107177d1e85d31be778da49f9559261e9))
- Fix api path - ([286e707](https://github.com/sib-swiss/sparql-llm/commit/286e70739b582d93688c5b48e264d763b3b1fd74))
- Fix check - ([dee02fa](https://github.com/sib-swiss/sparql-llm/commit/dee02fa780164ceb06dbafd4f8fe58cbfeca7c4c))
- Fix qdrant grpc - ([8178bcf](https://github.com/sib-swiss/sparql-llm/commit/8178bcf1fdeb7fbd4ede13ffd5d3f3ae34fcf9b3))
- Fix podman network? - ([13ddcd3](https://github.com/sib-swiss/sparql-llm/commit/13ddcd3805bd428cd61d4615f46b79a6a985906f))
- Fix chunk to 500 - ([4fae33f](https://github.com/sib-swiss/sparql-llm/commit/4fae33fc74b5f37efa1e7bf1f51921e2c1e5b397))
- Fix dim - ([8ee5614](https://github.com/sib-swiss/sparql-llm/commit/8ee5614fd09e47eabf8028c1ce004575fd30dcbe))
- Fix - ([0895d9c](https://github.com/sib-swiss/sparql-llm/commit/0895d9c779b340e565e80b0fbe1b722bedf25f1a))
- Fix port - ([370d930](https://github.com/sib-swiss/sparql-llm/commit/370d930fd9057697e46353da9aa7e69b3c2b4cc4))
- Fix feedback btn - ([1448ca1](https://github.com/sib-swiss/sparql-llm/commit/1448ca16f4aaed149e04367ff0c26f4aefd71253))
- Fix issue when no query in answer - ([051d59d](https://github.com/sib-swiss/sparql-llm/commit/051d59d908f29e6f814db9d1cff688b955284a99))
- Fix validate - ([aa37133](https://github.com/sib-swiss/sparql-llm/commit/aa3713380e083beb895a8944d75fd9a9e11fab95))
- Fix check_logs notebook - ([ef077cf](https://github.com/sib-swiss/sparql-llm/commit/ef077cf8749a6365ec044e772079e40d108d2b68))
- Fix notebook - ([657a62a](https://github.com/sib-swiss/sparql-llm/commit/657a62a43dff3b61afd384a4de8421931efb0d1c))
- Fix - ([9aaea82](https://github.com/sib-swiss/sparql-llm/commit/9aaea8248bae795126c6ad59a0a8bdb15ba3fc57))
- Fix - ([f6ec3f4](https://github.com/sib-swiss/sparql-llm/commit/f6ec3f4537e31b95269e6c94a81b08ebcc12f810))
- Fix deps - ([62c2532](https://github.com/sib-swiss/sparql-llm/commit/62c2532b668af12aee1d2364b21be685e8dcc173))
- Fix optional type for 3.9 - ([6e372ca](https://github.com/sib-swiss/sparql-llm/commit/6e372ca17162e5c454deab2fe86620b4ce1935d1))
- Fix union types for 3.9 - ([7784b70](https://github.com/sib-swiss/sparql-llm/commit/7784b70aaf899364a0d8439b69a24963024eacef))
- Fix fix sparql query function - ([c7fac57](https://github.com/sib-swiss/sparql-llm/commit/c7fac572eb3806fe7b648461fc032c8fbecc9b98))
- Fix weird bug - ([593997e](https://github.com/sib-swiss/sparql-llm/commit/593997e5ba274fee9817384f4e034611a39ffcf6))
- Fix tests - ([d091e22](https://github.com/sib-swiss/sparql-llm/commit/d091e22479c21820fd14b7c42bc838fc032317a3))
- Fix global imports and bump to 0.0.3 - ([d858e57](https://github.com/sib-swiss/sparql-llm/commit/d858e574f854a0b259cd0c743c61261ca94f4fd1))
- Fix tailwind typo - ([5dd3ccb](https://github.com/sib-swiss/sparql-llm/commit/5dd3ccb7b27199966987ff7bc1fe446ff5617242))
- Fix eslint - ([43c159a](https://github.com/sib-swiss/sparql-llm/commit/43c159a784c8297e9c2c663ed1066177e4f58ea3))
- Fix deployment - ([6161b00](https://github.com/sib-swiss/sparql-llm/commit/6161b00ab5b7788a414f7f1a81f780d87aea9898))
- Fix deployment - ([2ae949c](https://github.com/sib-swiss/sparql-llm/commit/2ae949cca1c6ba4b1b33b74be88536ac854b5343))
- Fix deployment - ([645af50](https://github.com/sib-swiss/sparql-llm/commit/645af509667b83611464d3a26e5da89132b9e205))
- Fix deployment - ([8cc2a28](https://github.com/sib-swiss/sparql-llm/commit/8cc2a28f931ff8dcba5e4b95c66fa73d1e13d580))
- Fix deployment - ([8f1444b](https://github.com/sib-swiss/sparql-llm/commit/8f1444b9b7a974379cadd83cbcfd00f0844bfc24))
- Fix deployment finally, podman is definitely poorly developed and broke continously - ([f62cce9](https://github.com/sib-swiss/sparql-llm/commit/f62cce913fafed58da3469851b6d0ff630c406ca))
- Fix deployment - ([b8c3398](https://github.com/sib-swiss/sparql-llm/commit/b8c33988550ab0e26e5aaef18af95cd1798b3f7b))
- Fixing request - ([35af41d](https://github.com/sib-swiss/sparql-llm/commit/35af41d080a07e4163ca70e9415ad72204dce031))
- Fix how retrieved docs are buffered - ([598ebad](https://github.com/sib-swiss/sparql-llm/commit/598ebade9201fcbdab8705c741733afb258478b6))
- Fix sparql query for void - ([19311d2](https://github.com/sib-swiss/sparql-llm/commit/19311d2c1ee16994ee9b21f282a90ab0549b4307))
- Fix indexing batch size nd increase timeout to overcome gRPC Deadline Exceeded error - ([12e4842](https://github.com/sib-swiss/sparql-llm/commit/12e48422480864e25b617c1ec5c395ebc0e7785e))
- Fix tests - ([71be9bf](https://github.com/sib-swiss/sparql-llm/commit/71be9bff920166f9b324df9b7984d8b2b0fe5afe))
- Fix tests deps - ([013249f](https://github.com/sib-swiss/sparql-llm/commit/013249fef074c77a82aa3556e331713deb119df9))
- Fix deploy workflow - ([789613c](https://github.com/sib-swiss/sparql-llm/commit/789613c50bf7bb9650248f2098bdaaf67beff318))
- Fix slides - ([7bbcc80](https://github.com/sib-swiss/sparql-llm/commit/7bbcc8089f9956cb5cb3d524cef17e09365bbd4d))
- Fix httpx logging to warnings - ([5323a52](https://github.com/sib-swiss/sparql-llm/commit/5323a52c0f1876872b089adcbd3a26cbc3fa768d))
- Fix podman url - ([520726d](https://github.com/sib-swiss/sparql-llm/commit/520726d66d1bed3f3ecd4502de12d2cf89722731))
- Fix feedback request - ([2c060f3](https://github.com/sib-swiss/sparql-llm/commit/2c060f36bccc27c1309a2fe25eacfc09210ef411))
- Fix schema format - ([669ebf5](https://github.com/sib-swiss/sparql-llm/commit/669ebf543e00b9e0870b427480a1dae7a8386030))
- Fix required python version in mcp package and update podman deployment script, improve resources indexing - ([55dc5c3](https://github.com/sib-swiss/sparql-llm/commit/55dc5c365ec59f3ef79098c24dd3552a2a897a97))
- Make it work with Anthropic and Mistral through OpenRouter - ([cbeda1a](https://github.com/sib-swiss/sparql-llm/commit/cbeda1a491b99b7661ccebd000647be9c4e9503b))
- Fix example loader when query fail to parse - ([d73aded](https://github.com/sib-swiss/sparql-llm/commit/d73adedaa8f8eefc3c37f734b8b421fa89065097))
- Fix shape URIs when generating shex from void - ([e56eb39](https://github.com/sib-swiss/sparql-llm/commit/e56eb39d92f76f5c86f68764a38f274a3fcc1336))
- Langgraph node type annotation - ([412ac79](https://github.com/sib-swiss/sparql-llm/commit/412ac79ac631569e571db1551c91382e389ba04e))

### 📚 Documentation

- Update tutorial code - ([acd05ba](https://github.com/sib-swiss/sparql-llm/commit/acd05ba699d2dac3148accc43d148abd16bc0820))
- Improve tutorial - ([8710122](https://github.com/sib-swiss/sparql-llm/commit/871012275b8e733386d8fcded219db67b3e55ad9))
- Update tutorial - ([84bc550](https://github.com/sib-swiss/sparql-llm/commit/84bc550da87c6ccc5b32a41a0ccdac563eebb36e))
- Add contributing.md and improve readme - ([2aaeb7b](https://github.com/sib-swiss/sparql-llm/commit/2aaeb7b09b01c2ba03193a28a42ea8363b5d609a))

### 🚜 Refactor

- Fix some mypy warnings and add OpenRouter support - ([19d7a4b](https://github.com/sib-swiss/sparql-llm/commit/19d7a4b4c2012a3c8bc2595e85f5ed790d0d3ca8))
- Improve metrin kg description - ([013d36b](https://github.com/sib-swiss/sparql-llm/commit/013d36b4ebb61162811779687dd992ebc6b1e5bb))
- Replace curies-rs with curies - ([3ff54f5](https://github.com/sib-swiss/sparql-llm/commit/3ff54f5c9b439653a8c1fa98aee877122d4a9989))
- Delete src/expasy-mcp folder, now integrated in main agent API - ([22e8027](https://github.com/sib-swiss/sparql-llm/commit/22e8027bdd8be059f2ff0bd711388ea529051246))
- Move all code from expasy_agent directly in src/sparql_llm and use optional dependencies - ([3d0129c](https://github.com/sib-swiss/sparql-llm/commit/3d0129c5f3eec166e78e5c81ac727c27e99d924a))
- Move text2sparql in tests folder and fix its imports, delete src/expasy_agent - ([9302dcc](https://github.com/sib-swiss/sparql-llm/commit/9302dccde33bd75b9fafc470bb8da92a1dc138b2))

### 🛠️ Miscellaneous Tasks

- Fix some warnings - ([27c2eb7](https://github.com/sib-swiss/sparql-llm/commit/27c2eb760716fb07d280900c0cc600002d488105))
- Reindex instructions - ([067dd6f](https://github.com/sib-swiss/sparql-llm/commit/067dd6f4c990f4a899ce5777dcabff3c816021ee))
- Fmt - ([b59852b](https://github.com/sib-swiss/sparql-llm/commit/b59852baf4a98347b9e25bcf8f4e5012c58c68a0))
- Migrate from python 3.12 to 3.13 - ([5870169](https://github.com/sib-swiss/sparql-llm/commit/5870169bc7b798cd69987588b5ef83fabdbe36bc))
- Fix dependencies to enable deploying MCP server without need for extra deps as CLI - ([d050674](https://github.com/sib-swiss/sparql-llm/commit/d0506742d77bcd689e5997b77e52e58481f32fa8))
- Chore: improve logging
refactor: fmt - ([b30085b](https://github.com/sib-swiss/sparql-llm/commit/b30085bca269f677e0a726b68dbab1b258faecb6))
- Fix path in deploy.sh script - ([1d7ae5d](https://github.com/sib-swiss/sparql-llm/commit/1d7ae5dfb2368bd4a28042b2288f0c80bcd5753b))
- Fix port from production deployment in compose.yml - ([c7710e9](https://github.com/sib-swiss/sparql-llm/commit/c7710e94ed38da66adcdddea9799f8d8f97c0602))
- Readme update - ([9f48a9d](https://github.com/sib-swiss/sparql-llm/commit/9f48a9d8ab5ec1b6b114a09efa96214fec15815c))

### 🧪 Testing

- Test - ([91b7727](https://github.com/sib-swiss/sparql-llm/commit/91b7727cffea4a3184fa7ea9ea6c82b767c09a70))
- Test no onto - ([a3f57bc](https://github.com/sib-swiss/sparql-llm/commit/a3f57bcbe47d57f8a13b50fc3d393802324945b2))
- Test - ([d6bb942](https://github.com/sib-swiss/sparql-llm/commit/d6bb9427361b1075ccbcb155935472a461f16a3e))

<!-- generated by git-cliff -->
