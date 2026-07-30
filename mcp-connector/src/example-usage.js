/**
 * example-usage.js — a walking-skeleton smoke test.
 * Run with: npm run example
 * Edit TARGET_CONTAINER to a container the agent's WebID already has at
 * least Read access to (e.g. one the Pod owner created for this purpose).
 */

const { getAgentSession, closeSession } = require("./auth");
const podClient = require("./podClient");
const wacManager = require("./wacManager");

const TARGET_CONTAINER = "https://your-pod.example/hyperscope-agent-test/";

async function main() {
  const session = await getAgentSession();

  try {
    console.log(`Listing ${TARGET_CONTAINER} ...`);
    const contents = await podClient.listContainer(TARGET_CONTAINER, session);
    console.log(contents);

    const noteUrl = `${TARGET_CONTAINER}hello-from-agent.md`;
    console.log(`Writing ${noteUrl} ...`);
    await podClient.writeFile(
      noteUrl,
      `# Hello from the HyperScope agent\n\nWritten at ${new Date().toISOString()}\n`,
      "text/markdown",
      session
    );

    console.log(`Reading it back ...`);
    const file = await podClient.readFile(noteUrl, session);
    console.log(await file.text());

    console.log(`Checking who has access to the container ...`);
    const access = await wacManager.listAgentsWithAccess(TARGET_CONTAINER, session);
    console.log(access);
  } finally {
    await closeSession(session);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
