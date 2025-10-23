# Observe

> Find suggested actions for your workflows

## What is `observe()`?

```typescript  theme={null}
page.observe("Find the login button")
```

`observe` allows you to turn any page into a checklist of reliable, executable actions. It discovers key elements, ranks likely next steps, and returns structured actions (selector, method, args) you can run instantly with `act` or use to precisely target `extract` so workflows are faster, cheaper, and more resilient.

## Why use `observe()`?

<CardGroup cols={2}>
  <Card title="Explore" icon="compass" href="/basics/observe#observe-with-act">
    When you're unsure what's on a page or need to discover available actions
  </Card>

  <Card title="Plan" icon="map" href="/basics/observe#plan-ahead">
    When building complex workflows, plan ahead all the actions you'll need to take
  </Card>

  <Card title="Cache" icon="database" href="/best-practices/caching">
    When you want to remember actions for the future and avoid LLM calls
  </Card>

  <Card title="Validate" icon="check" href="/basics/observe#observe-with-act">
    Before performing critical actions to ensure elements exist
  </Card>
</CardGroup>

## Using `observe()`

Calling `observe` supercharges other Stagehand methods. Use it to plan workflows, speed up `act`, and precisely target `extract`. Using `observe` helps you explore what's possible on a page by giving you a list of suggested actions.

<CodeGroup>
  ```typescript TypeScript theme={null}
  // Plan & validate
  const buttons = await page.observe("Find the log in / sign up buttons");
  ```

  ```python Python theme={null}
  # Plan & validate
  buttons = await page.observe("Find the log in / sign up buttons")
  ```
</CodeGroup>

This will return a list of suggestions with the following structure

```json  theme={null}
{
  "selector": "xpath=/html/body/header/div/button[1]",
  "description": "Log in button in the top right corner",
  "method": "click",
  "arguments": []
}
```

### Observe with Act

You can **validate** the action (method, selector, arguments...) and then pass it to `act` to **avoid extra LLM inference**.

<Note>
  **Performance Tip**: Acting on multiple `observe` suggestions will minimize the number of LLM calls for multi-step actions and speed up your workflow 2-3x.
</Note>

<CodeGroup>
  ```typescript TypeScript theme={null}
  await page.act(buttons[0]); // No LLM!
  ```

  ```python Python theme={null}
  await page.act(buttons[0]) # No LLM!
  ```
</CodeGroup>

#### Plan ahead

You can use multiple suggestions from `observe` to preview a batch of actions. For example, when filling a form you could ask `observe` to find all the fields and then pass them in to `act`. **Call the LLM once, act multiple times**.

<CodeGroup>
  ```typescript TypeScript theme={null}
  const fields = await page.observe("Find all the fields in the form");
  for (const field of fields) {
    await page.act(field); // No LLM!
  }
  ```

  ```python Python theme={null}
  fields = await page.observe("Find all the fields in the form")
  for field in fields:
    await page.act(field) # No LLM!
  ```
</CodeGroup>

### Observe and Extract

Using `observe` to focus `extract` on a specific section of the page (like a table, a form, a list...) minimizes the context needed for an extraction.

<Tip>
  **Savings Tip**: Pass the selector to `extract` to reduce LLM token usage by 10x for verbose websites!
</Tip>

<CodeGroup>
  ```typescript TypeScript theme={null}
  // Use observe to validate elements before extraction
  const [ table ] = await page.observe("Find the data table");

  const { data } = await page.extract({
    instruction: "Extract data from the table",
    schema: z.object({
      data: z.string()
    }),
    selector: table.selector // Reduce context scope needed for extraction
  });
  ```

  ```python Python theme={null}
  # Use observe to find the specific section (table, form, list, etc.)
  tables = await page.observe("Find the data table")
  table = tables[0]  # Get the first suggestion

  # Extract data using the selector to minimize context
  extraction = await page.extract(
      "Extract data from the table",
      schema=TableData,  # Pydantic schema
      selector=table.selector  # Focus extraction on just this table
  )
  ```
</CodeGroup>

## Best Practices

### Choose the right commands

<Tabs>
  <Tab title="Do this">
    * Use `observe` when a yes/no answer will gate an action (e.g., "Find the Submit button"), then conditionally `act`.
    * Use `extract` for information-only questions (e.g., "What’s the page title?", "How many results are listed?").
  </Tab>

  <Tab title="Don't do this">
    * Don’t call `extract` to locate elements you plan to click next.
    * Don’t call `observe` to answer info-only questions that won’t lead to an action.
  </Tab>
</Tabs>

* **Discover and plan with `observe`**: Use `observe("Find…")` to map actionable elements and preview next steps.
* **Scope `extract` with selectors from `observe`**: First `observe("Find the data table")`, then pass `selector` to `extract` to reduce tokens and boost accuracy.

### Conserve LLM tokens

Optimize performance by directly passing `ObserveResult` to `act` (e.g., `await page.act(results[0])`) to save LLM tokens. Batch operations by using `observe` once to find elements, then act on each. Cache and reuse stable `observe` results for familiar pages, using self-healing if layouts change.

<Card title="Build your own cache" icon="database" href="/best-practices/caching">
  Check out the guide on how to build your own action cache
</Card>

### Improve Accuracy

Be precise with instructions, e.g., "Find the primary CTA in the hero" for better results. For iframes, set `iframes: true` and wait for `networkidle`. Use `observe` selectors in `extract` to limit context.

<Card title="Prompting Best Practices" icon="robot" href="/best-practices/prompting-best-practices">
  Check out the guide on how to improve the accuracy of your results
</Card>

### Action Validation

Before performing critical actions, validate the suggestion's `method`, `selector`, and `arguments` to prevent misclicks. If a direct `act` fails, use `observe` with the same prompt to verify the method, then proceed with the suggested action.

<CodeGroup>
  ```typescript TypeScript theme={null}
  const prompt = "click the submit button";
  const expectedMethod = "click";

  try {
    await page.act(prompt);
  } catch (error) {
    if (error.message.includes("method not supported")) {
      // Observe the same prompt to get the planned action
      const [action] = await page.observe(prompt);
      
      if (action && action.method === expectedMethod) {
        await page.act(action);
      } else {
        throw new Error(`Unsupported method: expected "${expectedMethod}", got "${action?.method}"`);
      }
    } else {
      throw error;
    }
  }
  ```

  ```python Python theme={null}
  prompt = "click the submit button"
  expected_method = "click"

  try:
      await page.act(prompt)
  except Exception as error:
      if "method not supported" in str(error):
          # Observe the same prompt to get the planned action
          results = await page.observe(prompt)
          
          if results and results[0].method == expected_method:
              await page.act(results[0])
          else:
              method = results[0].method if results else "unknown"
              raise Exception(f'Unsupported method: expected "{expected_method}", got "{method}"')
      else:
          raise error
  ```
</CodeGroup>

## Troubleshooting

<AccordionGroup>
  <Accordion title="No elements found">
    **Problem**: `observe` returns empty array

    **Solutions**:

    * Make sure the element exists on the page
    * Use explicit instructions to find the element
    * Ensure page has fully loaded
    * Look at the [debugging workflows](/configuration/logging) logs, if the element is there then the LLM might be hallucinating/not catching it.
  </Accordion>

  <Accordion title="Inaccurate element descriptions">
    **Problem**: Descriptions don't match actual elements

    **Solutions**:

    * Use more capable models: check [evals](https://stagehand.dev/evals) for the best models for your use case
    * Provide more specific instructions
    * Log inference to file (see [debugging workflows](/configuration/logging)) to get an LLM trace
  </Accordion>

  <Accordion title="Wrong method identified">
    **Problem**: The method identified is not valid

    **Solutions**:

    * Check the [supported actions](/basics/act)
    * Provide more specific instructions
    * Validate the method, if invalid override with one of the supported ones
  </Accordion>
</AccordionGroup>

## Next Steps

<CardGroup cols={2}>
  <Card title="Act Overview" icon="play" href="/basics/act">
    Execute actions efficiently using `observe` results
  </Card>

  <Card title="Extract Data" icon="download" href="/basics/extract">
    Extract structured data from observed elements
  </Card>

  <Card title="Observability" icon="chart-line" href="/configuration/observability">
    Monitor and debug observation performance
  </Card>

  <Card title="Optimizations" icon="star" href="/best-practices/caching">
    Advanced optimization and patterns techniques
  </Card>
</CardGroup>


---

# observe()

> Complete API reference for the observe() method

<CardGroup cols={1}>
  <Card title="Observe" icon="magnifying-glass" href="/basics/observe">
    See how to use observe() to discover actionable elements and analyze web page structure
  </Card>
</CardGroup>

### Method Signatures

<Tabs>
  <Tab title="TypeScript">
    ```typescript
    // With ObserveOptions
    await page.observe(options: ObserveOptions): Promise<ObserveResult[]>

    // String instruction shorthand
    await page.observe(instruction: string): Promise<ObserveResult[]>
    ```

    **ObserveOptions Interface:**

    ```typescript
    interface ObserveOptions {
      instruction?: string;
      modelName?: AvailableModel;
      modelClientOptions?: ClientOptions;
      domSettleTimeoutMs?: number;
      drawOverlay?: boolean;
      iframes?: boolean;
    }
    ```
  </Tab>

  <Tab title="Python">
    ```python
    # With parameters
    await page.observe(
        instruction: str,
        dom_settle_timeout_ms: int = None,
        iframes: bool = None,
        model_name: AvailableModel = None,
        model_client_options: Dict = None
    ) -> List[ObserveResult]
    ```
  </Tab>
</Tabs>

### Parameters

<ParamField path="instruction" type="string" optional>
  Natural language description of elements or actions to discover.
</ParamField>

<ParamField path="modelName" type="AvailableModel" optional>
  Override the default LLM model for this observation.
</ParamField>

<ParamField path="modelClientOptions" type="ClientOptions" optional>
  Model-specific configuration options.
</ParamField>

<ParamField path="domSettleTimeoutMs" type="number" optional>
  Maximum time to wait for DOM to stabilize before analysis.

  **Default:** `30000`
</ParamField>

<ParamField path="drawOverlay" type="boolean" optional>
  Whether to draw visual overlays on discovered elements (debugging).

  **Default:** `false`
</ParamField>

<ParamField path="iframes" type="boolean" optional>
  Set to `true` to search within iframes.

  **Default:** `false`
</ParamField>

### Response

**Returns:** `Promise<ObserveResult[]>`

Array of discovered actionable elements, ordered by relevance.

**ObserveResult Interface:**

```typescript
interface ObserveResult {
  selector: string;        // XPath selector to locate element
  description: string;     // Human-readable description
  method?: string;         // Suggested action method
  arguments?: string[];    // Additional action parameters
}
```

<ParamField path="selector" type="string">
  XPath selector that precisely locates the element.
</ParamField>

<ParamField path="description" type="string">
  Human-readable description of the element and its purpose.
</ParamField>

<ParamField path="method" type="string" optional>
  Suggested interaction method: `"click"`, `"fill"`, `"selectOptionFromDropdown"`, `"nextChunk"`, `"scrollTo"`, `"prevChunk"`.
</ParamField>

<ParamField path="arguments" type="string[]" optional>
  Additional parameters for the suggested action.
</ParamField>

### Code Examples

<CodeGroup>
  ```typescript TypeScript
  // Basic element discovery
  const buttons = await page.observe("find all clickable buttons");
  const formFields = await page.observe("locate form input fields");

  // Advanced configuration
  const elements = await page.observe({
    instruction: "find important call-to-action buttons",
    modelName: "gpt-4.1-mini",
    domSettleTimeoutMs: 45000,
    drawOverlay: true
  });

  // Working with results
  const [loginButton] = await page.observe("find the login button");
  if (loginButton) {
    console.log("Found:", loginButton.description);
    console.log("Selector:", loginButton.selector);
    await page.act(loginButton); // Execute the action
  }

  // Filter results
  const submitButtons = await page.observe("find all submit buttons");
  const primarySubmit = submitButtons.find(btn => 
    btn.description.toLowerCase().includes('primary')
  );

  // Iframe search
  const iframeElements = await page.observe({
    instruction: "find form fields inside the iframe",
    iframes: true
  });
  ```

  ```python Python
  # Basic element discovery
  buttons = await page.observe("find all clickable buttons")
  form_fields = await page.observe("locate the form fields")

  # Advanced configuration  
  elements = await page.observe(
      instruction="find important call-to-action buttons",
      model_name="gpt-4.1-mini",
      dom_settle_timeout_ms=45000
  )

  # Working with results
  login_buttons = await page.observe("find the login button")
  if login_buttons:
      button = login_buttons[0]
      print("Found:", button.description)
      print("Selector:", button.selector)
      await page.act(button)  # Execute the action

  # Filter results
  submit_buttons = await page.observe("find all submit buttons")
  primary_submit = next((
      btn for btn in submit_buttons 
      if 'primary' in btn.description.lower()
  ), None)

  # Iframe search
  iframe_elements = await page.observe(
      instruction="find the form fields inside the iframe",
      iframes=True
  )
  ```
</CodeGroup>

### Integration Patterns

<CodeGroup>
  ```typescript TypeScript
  // Observe → Act workflow
  const actions = await page.observe("find checkout elements");
  for (const action of actions) {
    await page.act(action);
    await page.waitForTimeout(1000);
  }

  // Observe → Extract workflow
  const tables = await page.observe("find data tables");
  if (tables.length > 0) {
    const data = await page.extract({
      instruction: "extract the table data",
      selector: tables[0].selector,
      schema: DataSchema
    });
  }

  // Element validation
  const requiredElements = await page.observe("find the login form");
  if (requiredElements.length === 0) {
    throw new Error("Login form not found");
  }
  ```

  ```python Python
  # Observe → Act workflow  
  actions = await page.observe("find checkout elements")
  for action in actions:
      await page.act(action)
      await page.wait_for_timeout(1000)

  # Observe → Extract workflow
  tables = await page.observe("find data tables")
  if tables:
      data = await page.extract(
          instruction="extract the table data",
          selector=tables[0].selector,
          schema=DataSchema
      )

  # Element validation
  required_elements = await page.observe("find login form")
  if not required_elements:
      raise Exception("Login form not found")
  ```
</CodeGroup>
