# Extract

> Extract structured data from a webpage

## What is `extract()`?

```typescript
page.extract("extract the name of the repository");
```

`extract` grabs structured data from a webpage. You can define your schema with [zod](https://github.com/colinhacks/zod) (TypeScript) or [pydantic](https://github.com/pydantic/pydantic) (Python). If you do not want to define a schema, you can also call `extract` with just a [natural language prompt](#extract-with-just-a-prompt), or call `extract` [with no parameters](#extract-with-no-parameters).

## Why use `extract()`?

<CardGroup cols={2}>
  <Card title="Structured" icon="brackets-curly" href="#list-of-objects-extraction">
    Turn messy webpage data into clean objects that follow a schema.
  </Card>

  <Card title="Resilient" icon="dumbbell" href="#extract-with-context">
    Build resilient extractions that don't break when the website changes
  </Card>
</CardGroup>

<Note>
  For TypeScript, the extract schemas are defined using zod schemas.

  For Python, the extract schemas are defined using pydantic models.
</Note>

## Using `extract()`

### Single object Extraction

Here is how an `extract` call might look for a single object:

<CodeGroup>
  ```typescript TypeScript
  import { z } from 'zod/v3';

  const item = await page.extract({
    instruction: "extract the price of the item",
    schema: z.object({
      price: z.number(),
    }),
  });
  ```

  ```python Python
  from pydantic import BaseModel

  class Extraction(BaseModel):
      price: float

  item = await page.extract(
      "extract the price of the item", 
      schema=Extraction
  )
  ```
</CodeGroup>

Your output schema will look like:

```Example
{ price: number }
```

### List of objects Extraction

Here is how an `extract` call might look for a list of objects.

<CodeGroup>
  ```typescript TypeScript
  import { z } from 'zod/v3';

  const apartments = await page.extract({
    instruction:
      "Extract ALL the apartment listings and their details, including address, price, and square feet.",
    schema: z.object({
      list_of_apartments: z.array(
        z.object({
          address: z.string(),
          price: z.string(),
          square_feet: z.string(),
        }),
      ),
    })
  })

  console.log("the apartment list is: ", apartments);
  ```

  ```python Python
  from pydantic import BaseModel

  class Apartment(BaseModel):
      address: str
      price: str
      square_feet: str

  class Apartments(BaseModel):
      list_of_apartments: list[Apartment]

  apartments = await page.extract(
      "Extract ALL the apartment listings and their details as a list, including address, price, and square feet for each apartment",
      schema=Apartments
  )

  print("the apartment list is: ", apartments)
  ```
</CodeGroup>

Your output schema will look like:

```Example
list_of_apartments: [
    {
      address: "street address here",
      price: "$1234.00",
      square_feet: "700"
    },
    {
        address: "another address here",
        price: "1010.00",
        square_feet: "500"
    },
    ...
]
```

### Prompt-only Extraction

You can call `extract` with just a natural language prompt:

<CodeGroup>
  ```typescript TypeScript
  const result = await page.extract("extract the name of the repository");
  ```

  ```python Python
  result = await page.extract("extract the name of the repository")
  ```
</CodeGroup>

When you call `extract` with just a prompt, your output schema will look like:

```Example
{ extraction: string }
```

### Extract with no parameters

Here is how you can call `extract` with no parameters.

<CodeGroup>
  ```typescript TypeScript
  const pageText = await page.extract();
  ```

  ```python Python
  page_text = await page.extract()
  ```
</CodeGroup>

Output schema:

```Example
{ page_text: string }
```

Calling `extract` with no parameters will return hierarchical tree representation of the root DOM. This will not be passed through an LLM. It will look something like this:

```
Accessibility Tree:
[0-2] RootWebArea: What is Stagehand? - 🤘 Stagehand
  [0-37] scrollable
    [0-118] body
      [0-241] scrollable
        [0-242] div
          [0-244] link: 🤘 Stagehand home page light logo
            [0-245] span
              [0-246] StaticText: 🤘 Stagehand
              [0-247] StaticText: home page
```

## Best practices

### Extract with Context

You can provide additional context to your schema to help the model extract the data more accurately.

<CodeGroup>
  ```typescript TypeScript
  import { z } from 'zod/v3';

  const apartments = await page.extract({
   instruction:
     "Extract ALL the apartment listings and their details, including address, price, and square feet.",
   schema: z.object({
     list_of_apartments: z.array(
       z.object({
         address: z.string().describe("the address of the apartment"),
         price: z.string().describe("the price of the apartment"),
         square_feet: z.string().describe("the square footage of the apartment"),
       }),
     ),
   })
  })
  ```

  ```python Python
  from pydantic import BaseModel, Field

  class Apartment(BaseModel):
      address: str = Field(..., description="the address of the apartment")
      price: str = Field(..., description="the price of the apartment")
      square_feet: str = Field(..., description="the square footage of the apartment")

  class Apartments(BaseModel):
      list_of_apartments: list[Apartment]

  apartments = await page.extract(
      "Extract ALL the apartment listings and their details as a list. For each apartment, include: the address of the apartment, the price of the apartment, and the square footage of the apartment",
      schema=Apartments
  )
  ```
</CodeGroup>

### Link Extraction

<Note>
  To extract links or URLs, in the TypeScript version of Stagehand, you'll need to define the relevant field as `z.string().url()`.
  In Python, you'll need to define it as `HttpUrl`.
</Note>

Here is how an `extract` call might look for extracting a link or URL. This also works for image links.

<CodeGroup>
  ```typescript TypeScript
  import { z } from 'zod/v3';

  const extraction = await page.extract({
    instruction: "extract the link to the 'contact us' page",
    schema: z.object({
      link: z.string().url(), // note the usage of z.string().url() here
    }),
  });

  console.log("the link to the contact us page is: ", extraction.link);
  ```

  ```python Python
  from pydantic import BaseModel, HttpUrl

  class Extraction(BaseModel):
      link: HttpUrl # note the usage of HttpUrl here

  extraction = await page.extract(
      "extract the link to the 'contact us' page", 
      schema=Extraction
  )

  print("the link to the contact us page is: ", extraction.link)
  ```
</CodeGroup>

<Tip>
  Inside Stagehand, extracting links works by asking the LLM to select an ID. Stagehand looks up that ID in a mapping of IDs -> URLs. When logging the LLM trace, you should expect to see IDs. The actual URLs will be included in the final `ExtractResult`.
</Tip>

## Troubleshooting

<AccordionGroup>
  <Accordion title="Empty or partial results">
    **Problem**: `extract()` returns empty or incomplete data

    **Solutions**:

    * **Check your instruction clarity**: Make sure your instruction is specific and describes exactly what data you want to extract
    * **Verify the data exists**: Use `page.observe()` first to confirm the data is present on the page
    * **Wait for dynamic content**: If the page loads content dynamically, use `page.act("wait for the content to load")` before extracting

    **Solution: Wait for content before extracting**

    <CodeGroup>
      ```typescript TypeScript
      // Wait for content before extracting
      await page.act("wait for the product listings to load");
      const products = await page.extract({
        instruction: "extract all product names and prices",
        schema: z.object({
          products: z.array(z.object({
            name: z.string(),
            price: z.string()
          }))
        })
      });
      ```

      ```python Python
      # Wait for content before extracting
      await page.act("wait for the product listings to load")
      products = await page.extract(
          "extract all product names and prices",
          schema=ProductList
      )
      ```
    </CodeGroup>
  </Accordion>

  <Accordion title="Schema validation errors">
    **Problem**: Getting schema validation errors or type mismatches

    **Solutions**:

    * **Use optional fields**: Make fields optional with `z.optional()` (TypeScript) or `Optional[type]` (Python) if the data might not always be present
    * **Use flexible types**: Consider using `z.string()` instead of `z.number()` for prices that might include currency symbols
    * **Add descriptions**: Use `.describe()` (TypeScript) or `Field(description="...")` (Python) to help the model understand field requirements

    **Solution: More flexible schema**

    <CodeGroup>
      ```typescript TypeScript
      const schema = z.object({
        price: z.string().describe("price including currency symbol, e.g., '$19.99'"),
        availability: z.string().optional().describe("stock status if available"),
        rating: z.number().optional()
      });
      ```

      ```python Python
      class FlexibleProduct(BaseModel):
          price: str = Field(description="price including currency symbol, e.g., '$19.99'")
          availability: Optional[str] = Field(default=None, description="stock status if available")
          rating: Optional[float] = None
      ```
    </CodeGroup>
  </Accordion>

  <Accordion title="Inconsistent results">
    **Problem**: Extraction results vary between runs

    **Solutions**:

    * **Be more specific in instructions**: Instead of "extract prices", use "extract the numerical price value for each item"
    * **Use context in schema descriptions**: Add field descriptions to guide the model
    * **Combine with observe**: Use `page.observe()` to understand the page structure first

    **Solution: Validate with observe first**

    <CodeGroup>
      ```typescript TypeScript
      // First observe to understand the page structure
      const elements = await page.observe("find all product listings");
      console.log("Found elements:", elements.map(e => e.description));

      // Then extract with specific targeting
      const products = await page.extract({
        instruction: "extract name and price from each product listing shown on the page",
        schema: z.object({
          products: z.array(z.object({
            name: z.string().describe("the product title or name"),
            price: z.string().describe("the price as displayed, including currency")
          }))
        })
      });
      ```

      ```python Python
      # First observe to understand the page structure
      elements = await page.observe("find all product listings")
      print("Found elements:", [e.description for e in elements])

      # Then extract with specific targeting
      products = await page.extract(
          "extract name and price from each product listing shown on the page",
          schema=ProductSchema
      )
      ```
    </CodeGroup>
  </Accordion>

  <Accordion title="Performance issues">
    **Problem**: Extraction is slow or timing out

    **Solutions**:

    * **Reduce scope**: Extract smaller chunks of data in multiple calls rather than everything at once
    * **Use targeted instructions**: Be specific about which part of the page to focus on
    * **Consider pagination**: For large datasets, extract one page at a time
    * **Increase timeout**: Use `timeoutMs` parameter for complex extractions

    **Solution: Break down large extractions**

    <CodeGroup>
      ```typescript TypeScript
      // Instead of extracting everything at once
      const allData = [];
      const pageNumbers = [1, 2, 3, 4, 5];

      for (const pageNum of pageNumbers) {
        await page.act(`navigate to page ${pageNum}`);
        
        const pageData = await page.extract({
          instruction: "extract product data from the current page only",
          schema: ProductPageSchema,
          timeoutMs: 60000 // 60 second timeout
        });
        
        allData.push(...pageData.products);
      }
      ```

      ```python Python
      # Instead of extracting everything at once
      all_data = []
      page_numbers = [1, 2, 3, 4, 5]

      for page_num in page_numbers:
          await page.act(f"navigate to page {page_num}")
          
          page_data = await page.extract(
              "extract product data from the current page only",
              schema=ProductPageSchema,
              timeout_ms=60000  # 60 second timeout
          )
          
          all_data.extend(page_data.products)
      ```
    </CodeGroup>
  </Accordion>
</AccordionGroup>

## Next steps

<CardGroup cols={2}>
  <Card title="Act" icon="play" href="/basics/act">
    Execute actions efficiently using observe results
  </Card>

  <Card title="Observe" icon="magnifying-glass" href="/basics/observe">
    Analyze pages with observe()
  </Card>
</CardGroup>

# extract()

> Complete API reference for the extract() method

<CardGroup cols={1}>
  <Card title="Extract" icon="ufo-beam" href="/basics/extract">
    See how to use extract() to extract structured data from web pages
  </Card>
</CardGroup>

### Method Signatures

<Tabs>
  <Tab title="TypeScript">
    ```typescript
    // With schema and options
    await page.extract<T extends z.AnyZodObject>(options: ExtractOptions<T>): Promise<ExtractResult<T>>

    // String instruction only
    await page.extract(instruction: string): Promise<{ extraction: string }>

    // No parameters (raw page content)
    await page.extract(): Promise<{ page_text: string }>
    ```

    **ExtractOptions Interface:**

    ```typescript
    interface ExtractOptions<T extends z.AnyZodObject> {
      instruction?: string;
      schema?: T;
      modelName?: AvailableModel;
      modelClientOptions?: ClientOptions;
      domSettleTimeoutMs?: number;
      selector?: string;
      iframes?: boolean;
    }

    type ExtractResult<T> = z.infer<T>;
    ```
  </Tab>

  <Tab title="Python">
    ```python
    # With schema and parameters
    await page.extract(
        instruction: str = None,
        schema: BaseModel = None,
        selector: str = None,
        iframes: bool = None,
        model_name: AvailableModel = None,
        model_client_options: Dict = None,
        dom_settle_timeout_ms: int = None
    ) -> ExtractResult

    # String instruction only
    await page.extract(instruction: str) -> Dict[str, str]

    # No parameters (raw page content)
    await page.extract() -> Dict[str, str]
    ```
  </Tab>
</Tabs>

### Parameters

<ParamField path="instruction" type="string" optional>
  Natural language description of what data to extract.
</ParamField>

<ParamField path="schema" type="z.ZodSchema | BaseModel" optional>
  Type schema defining the structure of data to extract. Ensures type safety and validation.
</ParamField>

<ParamField path="selector" type="string" optional>
  XPath selector to limit extraction scope. Reduces token usage and improves accuracy.
</ParamField>

<ParamField path="iframes" type="boolean" optional>
  Set to `true` if content exists within iframes.

  **Default:** `false`
</ParamField>

<ParamField path="modelName" type="AvailableModel" optional>
  Override the default LLM model for this extraction.
</ParamField>

<ParamField path="modelClientOptions" type="ClientOptions" optional>
  Model-specific configuration options.
</ParamField>

<ParamField path="domSettleTimeoutMs" type="number" optional>
  Maximum time to wait for DOM to stabilize.

  **Default:** `30000`
</ParamField>

### Response Types

<Tabs>
  <Tab title="With Schema">
    **Returns:** `Promise<ExtractResult<T>>` where T matches your schema

    The returned object will be strictly typed according to your schema definition.
  </Tab>

  <Tab title="String Only">
    **Returns:** `Promise<{ extraction: string }>`

    Simple string extraction without schema validation.
  </Tab>

  <Tab title="No Parameters">
    **Returns:** `Promise<{ page_text: string }>`

    Raw accessibility tree representation of page content.
  </Tab>
</Tabs>

### Code Examples

<Tabs>
  <Tab title="Single Object">
    <CodeGroup>
      ```typescript TypeScript
      import { z } from 'zod';

      // Schema definition
      const ProductSchema = z.object({
        name: z.string(),
        price: z.number(),
        inStock: z.boolean()
      });

      // Extraction
      const product = await page.extract({
        instruction: "extract product details",
        schema: ProductSchema
      });
      ```

      ```python Python
      from pydantic import BaseModel

      # Schema definition
      class Product(BaseModel):
          name: str
          price: float
          in_stock: bool

      # Extraction
      product = await page.extract(
          instruction="extract product details",
          schema=Product
      )
      ```
    </CodeGroup>

    #### Example Response

    ```json
    {
      "name": "Product Name",
      "price": 100,
      "inStock": true
    }
    ```
  </Tab>

  <Tab title="Arrays">
    <CodeGroup>
      ```typescript TypeScript
      import { z } from 'zod';

      // Schema definition
      const ApartmentListingsSchema = z.object({
        apartments: z.array(z.object({
          address: z.string(),
          price: z.string(),
          bedrooms: z.number()
        }))
      });

      // Extraction
      const listings = await page.extract({
        instruction: "extract all apartment listings", 
        schema: ApartmentListingsSchema
      });
      ```

      ```python Python
      from pydantic import BaseModel
      from typing import List

      # Schema definition
      class Apartment(BaseModel):
          address: str
          price: str
          bedrooms: int

      class ApartmentListings(BaseModel):
          apartments: List[Apartment]

      # Extraction
      listings = await page.extract(
          instruction="extract all apartment listings",
          schema=ApartmentListings
      )
      ```
    </CodeGroup>

    #### Example Response

    ```json
    {
      "apartments": [
        {
          "address": "123 Main St",
          "price": "$100,000",
          "bedrooms": 3
        },
        {
          "address": "456 Elm St",
          "price": "$150,000",
          "bedrooms": 2
        }
      ]
    }
    ```
  </Tab>

  <Tab title="URLs">
    <CodeGroup>
      ```typescript TypeScript
      import { z } from 'zod';

      // Schema definition
      const NavigationSchema = z.object({
        links: z.array(z.object({
          text: z.string(),
          url: z.string().url()  // URL validation
        }))
      });

      // Extraction
      const links = await page.extract({
        instruction: "extract navigation links",
        schema: NavigationSchema
      });
      ```

      ```python Python
      from pydantic import BaseModel, HttpUrl
      from typing import List

      # Schema definition
      class NavLink(BaseModel):
          text: str
          url: HttpUrl  # URL validation

      class Navigation(BaseModel):
          links: List[NavLink]

      # Extraction
      links = await page.extract(
          instruction="extract navigation links", 
          schema=Navigation
      )
      ```
    </CodeGroup>

    #### Example Response

    ```json
    {
      "links": [
        {
          "text": "Home",
          "url": "https://example.com"
        }
      ]
    }
    ```
  </Tab>

  <Tab title="Scoped">
    <CodeGroup>
      ```typescript TypeScript
      import { z } from 'zod';

      const ProductSchema = z.object({
        name: z.string(),
        price: z.number(),
        description: z.string()
      });

      // Extract from specific page section
      const data = await page.extract({
        instruction: "extract product info from this section",
        selector: "xpath=/html/body/div/div",
        schema: ProductSchema
      });
      ```

      ```python Python
      from pydantic import BaseModel

      class Product(BaseModel):
          name: str
          price: float
          description: str

      # Extract from specific page section
      data = await page.extract(
          instruction="extract product info from this section",
          selector="xpath=/html/body/div/div",
          schema=Product
      )
      ```
    </CodeGroup>

    #### Example Response

    ```json
    {
      "name": "Product Name",
      "price": 100,
      "description": "Product description"
    }
    ```
  </Tab>

  <Tab title="Schema-less">
    <CodeGroup>
      ```typescript TypeScript
      // String only extraction
      const title = await page.extract("get the page title");
      // Returns: { extraction: "Page Title" }

      // Raw page content
      const content = await page.extract();
      // Returns: { page_text: "Accessibility Tree: ..." }
      ```

      ```python Python
      # String only extraction
      title = await page.extract("get the page title")
      # Returns: {"extraction": "Page Title"}

      # Raw page content
      content = await page.extract()
      # Returns: {"page_text": "Accessibility Tree: ..."}
      ```
    </CodeGroup>

    #### Example Response

    ```json
    {
      "extraction": "Page Title"
    }
    ```
  </Tab>

  <Tab title="Advanced">
    <CodeGroup>
      ```typescript TypeScript
      import { z } from 'zod';

      // Schema with descriptions and validation
      const ProductSchema = z.object({
        price: z.number().describe("Product price in USD"),
        rating: z.number().min(0).max(5).describe("Customer rating out of 5"),
        available: z.boolean().describe("Whether product is in stock"),
        tags: z.array(z.string()).optional()
      });

      // Nested schema
      const EcommerceSchema = z.object({
        product: z.object({
          name: z.string(),
          price: z.object({
            current: z.number(),
            original: z.number().optional()
          })
        }),
        reviews: z.array(z.object({
          rating: z.number(),
          comment: z.string()
        }))
      });
      ```

      ```python Python
      from pydantic import BaseModel, Field
      from typing import Optional, List

      # Schema with descriptions and validation
      class Product(BaseModel):
          price: float = Field(description="Product price in USD")
          rating: float = Field(ge=0, le=5, description="Customer rating out of 5")
          available: bool = Field(description="Whether product is in stock")
          tags: Optional[List[str]] = None

      # Nested schema
      class Price(BaseModel):
          current: float
          original: Optional[float] = None

      class Review(BaseModel):
          rating: int
          comment: str

      class ProductDetails(BaseModel):
          name: str
          price: Price

      class EcommerceData(BaseModel):
          product: ProductDetails
          reviews: List[Review]
      ```
    </CodeGroup>

    #### Example Response

    ```json
    {
      "product": {
        "name": "Product Name",
        "price": {
          "current": 100,
          "original": 120
        }
      },
      "reviews": [
        {
          "rating": 4,
          "comment": "Great product!"
        }
      ]
    }
    ```
  </Tab>
</Tabs>
