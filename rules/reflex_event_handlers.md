# Reflex Event Handlers Guide for AI Agents

## Architecture Overview

When developing web applications with Reflex, pages are declaratively described using various `rx.something` calls. These calls generate HTML markup that the browser renders.

**Key difference from traditional approaches**: Python code does NOT execute in the browser. Instead:
1. Browser sends an event to the server
2. Event handler executes on the server side
3. Handler modifies State variables (State vars)
4. Changes accumulate during handler execution
5. When handler completes, all changes are sent to the client via `StateUpdate` event
6. Browser receives updates and re-renders affected components

**Important architectural principle**: Pages depend on State, but State does NOT depend on pages. This means handlers cannot directly manipulate page elements - they can only modify State vars, and page elements reactively subscribe to these variables and update automatically.

## Event Handler Types

### 1. State Class Methods (Most Common)

Regular methods in a State class. These are the standard way to handle events.

**Requirements**:
- Method arguments must match the event signature exactly
- Decorator `@rx.event` is **recommended** and should always be used (even though technically optional for State methods)
- Bind to events using unbound method reference: `StateClassName.method_name`

**Example**:
```python
import reflex as rx

class State(rx.State):
    text: str = "Hello"
    counter: int = 0
    
    @rx.event
    def copy_text(self):
        """Simple handler with no arguments"""
        self.text = "Copied!"
    
    @rx.event
    def handle_input(self, value: str):
        """Handler that receives event data"""
        self.text = value
    
    @rx.event
    def increment(self):
        """Handler that modifies state"""
        self.counter += 1

def index():
    return rx.vstack(
        rx.text(State.text),
        rx.input(on_change=State.handle_input),
        rx.button("Copy", on_click=State.copy_text),
        rx.button(f"Count: {State.counter}", on_click=State.increment),
    )
```

### 2. Built-in Handlers (Special Events)

For simple cases, use built-in special events instead of writing custom methods.

**Common special events**:
- `rx.set_value(id, value)` - Set element value by ID
- `rx.set_clipboard(text)` - Copy text to clipboard
- See full list: https://reflex.dev/docs/api-reference/special-events/

**Example**:
```python
import reflex as rx

def index():
    return rx.hstack(
        rx.input(id="input1", placeholder="Type something"),
        rx.button("Clear", on_click=rx.set_value("input1", "")),
        rx.button("Copy 'Hello'", on_click=rx.set_clipboard("Hello World")),
    )
```

### 3. Decentralized Handlers (Since v0.7.1)

Functions outside State classes can be used as handlers.

**Requirements**:
- Must be decorated with `@rx.event`
- First argument must be a State class instance

**Example**:
```python
import reflex as rx

class State(rx.State):
    message: str = ""

@rx.event
def external_handler(state: State, text: str):
    """Handler defined outside the State class"""
    state.message = f"Received: {text}"

def index():
    return rx.vstack(
        rx.text(State.message),
        rx.input(on_change=external_handler),
    )
```

### 4. Lambda Expressions

Lambdas can be used but with important restrictions.

**Critical limitations**:
- Lambda executes in a different context than the Python code generating the page
- CANNOT access outer scope variables directly
- Can ONLY call State methods and set state variables
- Useful for adding custom parameters to event handlers

**Example**:
```python
import reflex as rx

class State(rx.State):
    field_values: dict[str, str] = {}
    
    @rx.event
    def handle_update(self, field_name: str, value: str):
        """Universal handler that receives field name and value"""
        self.field_values[field_name] = value

def index():
    return rx.vstack(
        rx.input(
            placeholder="Field 1",
            on_change=lambda v: State.handle_update("field1", v)
        ),
        rx.input(
            placeholder="Field 2", 
            on_change=lambda v: State.handle_update("field2", v)
        ),
        rx.text(f"Values: {State.field_values}"),
    )
```

### 5. Partial Handler Invocation (Since v0.5.0)

Cleaner alternative to lambdas for adding custom parameters.

**How it works**: Add custom parameters at the beginning of the argument list, and Reflex will automatically curry the function.

**Example (equivalent to lambda above)**:
```python
import reflex as rx

class State(rx.State):
    field_values: dict[str, str] = {}
    
    @rx.event
    def handle_update(self, field_name: str, value: str):
        """Custom param first, event param second"""
        self.field_values[field_name] = value

def index():
    return rx.vstack(
        # Cleaner than lambda - no need for lambda wrapper
        rx.input(
            placeholder="Field 1",
            on_change=State.handle_update("field1")  # Partial application
        ),
        rx.input(
            placeholder="Field 2",
            on_change=State.handle_update("field2")  # Partial application
        ),
        rx.text(f"Values: {State.field_values}"),
    )
```

## Complete Working Example

Here's a comprehensive example demonstrating all handler types:

```python
import reflex as rx

class DemoState(rx.State):
    # State variables
    message: str = "Welcome"
    counter: int = 0
    input_value: str = ""
    field_data: dict[str, str] = {}
    
    # Type 1: Regular State method
    @rx.event
    def reset_all(self):
        """Reset all state to defaults"""
        self.message = "Reset!"
        self.counter = 0
        self.input_value = ""
        self.field_data = {}
    
    # Type 1: Method with event argument
    @rx.event
    def update_message(self, text: str):
        """Update message from input"""
        self.message = text
    
    # Type 1: Simple increment
    @rx.event
    def increment(self):
        """Increment counter"""
        self.counter += 1
    
    # Type 5: Handler for partial invocation
    @rx.event
    def save_field(self, field_name: str, value: str):
        """Save field value with custom field name"""
        self.field_data[field_name] = value

# Type 3: Decentralized handler
@rx.event
def external_multiplier(state: DemoState):
    """External handler that multiplies counter"""
    state.counter *= 2

def index():
    return rx.container(
        rx.vstack(
            rx.heading("Reflex Event Handlers Demo", size="lg"),
            
            # Display current state
            rx.text(f"Message: {DemoState.message}"),
            rx.text(f"Counter: {DemoState.counter}"),
            rx.text(f"Field Data: {DemoState.field_data}"),
            
            rx.divider(),
            
            # Type 1: Regular handlers
            rx.input(
                placeholder="Type to update message",
                on_change=DemoState.update_message
            ),
            rx.button("Increment", on_click=DemoState.increment),
            rx.button("Reset All", on_click=DemoState.reset_all),
            
            rx.divider(),
            
            # Type 2: Built-in special events
            rx.hstack(
                rx.input(id="special_input", placeholder="Special input"),
                rx.button("Clear Input", on_click=rx.set_value("special_input", "")),
                rx.button("Copy Message", on_click=rx.set_clipboard(DemoState.message)),
            ),
            
            rx.divider(),
            
            # Type 3: Decentralized handler
            rx.button("Multiply Counter (External)", on_click=external_multiplier),
            
            rx.divider(),
            
            # Type 4: Lambda expression
            rx.input(
                placeholder="Field with lambda",
                on_change=lambda v: DemoState.save_field("lambda_field", v)
            ),
            
            # Type 5: Partial invocation (cleaner alternative)
            rx.input(
                placeholder="Name field",
                on_change=DemoState.save_field("name")
            ),
            rx.input(
                placeholder="Email field",
                on_change=DemoState.save_field("email")
            ),
            
            spacing="4",
        ),
        padding="4",
    )

app = rx.App()
app.add_page(index)
```

## Best Practices for AI Agents

1. **Always use `@rx.event` decorator** on all State methods that serve as event handlers - this is the recommended practice
2. **Prefer State methods** (Type 1) for most cases - they're the most straightforward
3. **Use special events** (Type 2) for simple operations like clearing inputs or copying to clipboard
4. **Use partial invocation** (Type 5) instead of lambdas when adding custom parameters - it's cleaner
5. **Remember**: Handlers modify State vars, NOT page elements directly
6. **State is independent**: Don't try to access page-specific information in handlers

## Documentation
https://reflex.dev/docs/events/event-arguments/
