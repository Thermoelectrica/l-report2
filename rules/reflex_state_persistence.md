# Reflex State Persistence Guide for AI Agents

## Overview

Reflex provides multiple ways to store and persist data, each with different scopes and durability characteristics. Understanding these differences is critical for choosing the right storage mechanism.

## Storage Types Comparison

| Type | Scope | Survives Page Refresh | Survives Server Restart | Survives Tab Close | Shared Across Tabs | Immediate Sync | Data Types | Usable in UI |
|------|-------|---------------------|----------------------|---------------------|-------------------|----------------|-----------|--------------|
| **Page-only values** | Single page render | ❌ No | ❌ No | ❌ No | ❌ No | N/A | Any Python type | ✅ Yes |
| **Public State vars** | Per browser tab | ✅ Yes | ❌ No | ❌ No | ❌ No | N/A | Serializable types | ✅ Yes |
| **Private State vars** | Per browser tab | ✅ Yes | ❌ No | ❌ No | ❌ No | N/A | Picklable types | ❌ No (server-only) |
| **SessionStorage** | Per browser tab | ✅ Yes | ✅ Yes | ❌ No | ❌ No | N/A | String only | ✅ Yes |
| **LocalStorage** | Per browser | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes (sync=True) | String only | ✅ Yes |
| **Cookie** | Per browser | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | String only | ✅ Yes |

**Note**: This guide covers standard state management using `rx.State` base class. For advanced use cases requiring **global state shared across all clients**, Reflex also provides `rx.SharedState` - a different parent class that creates truly global state. This is beyond the scope of this guide.

## 1. Page-Only Values (Non-Persistent)

**What**: Regular Python variables in your page function that are NOT part of State.

**Characteristics**:
- Evaluated once when page is rendered
- Lost on any page refresh or navigation
- Not reactive - changes don't trigger UI updates
- Useful for constants or one-time calculations

**Example**:
```python
import reflex as rx
from datetime import datetime

class State(rx.State):
    counter: int = 0

def index():
    # Page-only value - computed once per page load
    page_load_time = datetime.now().strftime("%H:%M:%S")
    
    return rx.vstack(
        rx.text(f"Page loaded at: {page_load_time}"),  # Never updates
        rx.text(f"Counter: {State.counter}"),  # Updates reactively
        rx.button("Increment", on_click=State.increment),
    )
```

**When to use**: Static content, initial calculations, constants that don't need to be reactive.

## 2. Public State Variables (Server-Side, Per-Tab, Sent to Client)

**What**: Variables defined in a State class with type annotations (without underscore prefix).

**Characteristics**:
- **Scope**: Each browser tab has its own isolated state instance
- **Durability**: Stored in server memory - lost on server restart
- **Persistence**: Survives page refresh within the same tab
- **Sharing**: NOT shared between browser tabs
- **Data types**: Must be serializable (str, int, float, bool, list, dict, etc.)
- **Client access**: Sent to client and can be used directly in UI components

**Example**:
```python
import reflex as rx

class State(rx.State):
    # Public state vars - sent to client, usable in UI
    username: str = ""
    items: list[str] = []
    counter: int = 0
    
    @rx.event
    def add_item(self, item: str):
        self.items.append(item)
    
    @rx.event
    def update_username(self, name: str):
        self.username = name
    
    @rx.event
    def increment(self):
        self.counter += 1

def index():
    return rx.vstack(
        rx.input(
            placeholder="Enter username",
            on_change=State.update_username
        ),
        # Can use public state vars directly in UI
        rx.text(f"Username: {State.username}"),
        rx.text(f"Items: {State.items}"),
        rx.text(f"Counter: {State.counter}"),
    )
```

**When to use**:
- Application state that needs to be displayed in UI
- Data that needs to be reactive and visible to the client
- Per-tab session data that doesn't need to survive server restarts
- Temporary calculations and user interactions

**Important**:
- Each tab is independent. Opening the same page in two tabs creates two separate State instances.
- Must be serializable to JSON (no complex Python objects like database connections, file handles, etc.)

## 3. Private State Variables (Server-Side, Per-Tab, Server-Only)

**What**: Variables defined in a State class with underscore prefix (e.g., `_variable_name`).

**Characteristics**:
- **Scope**: Each browser tab has its own isolated state instance
- **Durability**: Stored in server memory (or in redis) - might be lost on server restart. Not durable.
- **Persistence**: Survives page refresh within the same tab
- **Sharing**: NOT shared between browser tabs
- **Data types**: Must be picklable (most Python types except file handles, database connections, threads)
- **Client access**: NOT sent to client, server-only

**Example**:
```python
import reflex as rx
from datetime import datetime
from typing import Dict, List
import sqlite3

class State(rx.State):
    # Public state var - sent to client
    user_count: int = 0
    last_query_time: str = ""
    
    # Private state vars - server-only, picklable data structures
    _query_cache: Dict[str, List[dict]] = {}
    _last_access_times: Dict[str, datetime] = {}
    _processing_queue: List[str] = []
    
    @rx.event
    def cache_query_result(self, query: str):
        # Create DB connection when needed, don't store it
        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            results = cursor.execute(query).fetchall()
            
            # Store picklable results in private vars
            self._query_cache[query] = [dict(row) for row in results]
            self._last_access_times[query] = datetime.now()
            
            # Update public vars for UI
            self.user_count = len(results)
            self.last_query_time = datetime.now().strftime("%H:%M:%S")
    
    @rx.event
    def get_cached_result(self, query: str):
        # Use private var on server
        if query in self._query_cache:
            self.last_query_time = self._last_access_times[query].strftime("%H:%M:%S")
            self.user_count = len(self._query_cache[query])

def index():
    return rx.vstack(
        # Can only use public vars in UI
        rx.text(f"Result count: {State.user_count}"),
        rx.text(f"Last query: {State.last_query_time}"),
        # This would ERROR - cannot use private vars in UI:
        # rx.text(f"Cache: {State._query_cache}"),
        rx.button("Query DB", on_click=State.cache_query_result),
    )
```

**When to use**:
- **Complex data structures** that don't need to be visible to the client (nested dicts, lists)
- **Internal state** for server-side processing and caching
- **Sensitive data** that shouldn't be sent to the browser
- **Computed intermediate results** that are only needed on the server
- **Server-side queues, buffers, or temporary storage**

**Important**:
- Private vars must be picklable (no file handles, database connections, threads, locks)
- Cannot be used directly in UI components

## 4. SessionStorage (Client-Side, Per-Tab)

**What**: Browser's sessionStorage API wrapped by Reflex.

**Characteristics**:
- **Scope**: Per browser tab (like State vars)
- **Durability**: Stored in browser - survives page refresh
- **Persistence**: Cleared when tab/browser is closed
- **Sharing**: NOT shared between tabs
- **Data types**: Strings only (must convert complex types to stings manually)

**Key Difference from State vars**: 
- State vars are stored on the **server** (lost on server restart, but can use almost any Python type)
- SessionStorage is stored in the **browser** (survives server restart, but strings only)

**Example**:
```python
import reflex as rx
import json

class State(rx.State):
    # SessionStorage - survives server restart but not browser close
    session_data: str = rx.SessionStorage()
    
    @rx.event
    def save_to_session(self, value: str):
        self.session_data = value
    
    @rx.event
    def save_complex_data(self):
        # Must serialize to string
        data = {"user": "john", "score": 100}
        self.session_data = json.dumps(data)
    
    def get_parsed_data(self) -> dict:
        if self.session_data:
            return json.loads(self.session_data)
        return {}

def index():
    return rx.vstack(
        rx.input(
            placeholder="Save to session",
            on_change=State.save_to_session
        ),
        rx.text(f"Session data: {State.session_data}"),
        rx.button("Save Complex", on_click=State.save_complex_data),
    )
```

**When to use**:
- **Temporary per-tab data** that should be cleared when browser/tab is closed
- **Isolate data to a specific tab/window** (not shared across tabs)
- **Sensitive information** that shouldn't persist after the session ends
- **Per-session features** like form data, shopping carts, or multi-step processes
- **Persist state after Redis expiration** - can act as backup for server-side state that needs to survive longer than Redis TTL
- Data that should survive server restarts but not browser close

## 5. LocalStorage (Client-Side, Per-Browser, Durable)

**What**: Browser's localStorage API wrapped by Reflex.

**Characteristics**:
- **Scope**: Per browser (shared across all tabs - data is always shared)
- **Durability**: Stored in browser - survives browser close and server restart
- **Persistence**: Permanent until explicitly cleared
- **Sharing**: Data is shared across tabs, but `sync=True` is needed for immediate propagation of changes
- **Data types**: Strings only (must convert complex types to stings manually)

**Example**:
```python
import reflex as rx
import json

class State(rx.State):
    # LocalStorage - persists across browser restarts
    user_preferences: str = rx.LocalStorage()
    
    # With sync=True - changes propagate to other tabs immediately
    theme: str = rx.LocalStorage(sync=True)
    
    @rx.event
    def save_preferences(self, prefs: str):
        self.user_preferences = prefs
    
    @rx.event
    def toggle_theme(self):
        # This will update in all open tabs if sync=True
        self.theme = "dark" if self.theme == "light" else "light"
    
    @rx.event
    def save_user_settings(self, username: str, email: str):
        # Serialize complex data
        settings = {"username": username, "email": email}
        self.user_preferences = json.dumps(settings)
    
    def get_settings(self) -> dict:
        if self.user_preferences:
            return json.loads(self.user_preferences)
        return {}

def index():
    return rx.vstack(
        rx.text(f"Theme: {State.theme}"),
        rx.button("Toggle Theme", on_click=State.toggle_theme),
        rx.text(f"Preferences: {State.user_preferences}"),
    )
```

**When to use**:
- **Store larger amounts of data** (up to ~5MB, vs ~4KB for cookies)
- **Persist data indefinitely** (until explicitly deleted)
- **Share data between different tabs/windows** of your app
- **User preferences** that should be remembered across browser sessions
- Settings that should survive browser restarts
- Data that doesn't need to be sent with HTTP requests each time

**Important**:
- LocalStorage data is **always shared** across all tabs in the same browser (per-browser scope)
- Without `sync=True`, changes are stored and shared, but other tabs won't see updates until they refresh the page
- With `sync=True`, changes propagate immediately to all open tabs without requiring a refresh

## 6. Cookie (Client-Side, Per-Browser, Durable)

**What**: Browser cookies wrapped by Reflex.

**Characteristics**:
- **Scope**: Per browser (shared across all tabs - data is always shared)
- **Durability**: Stored as HTTP cookie - survives browser close and server restart
- **Persistence**: Can set expiration time
- **Sharing**: Data is shared across tabs, but changes are NOT propagated immediately (requires page refresh)
- **Data types**: Strings only (must serialize complex types)
- **Additional**: Sent with every HTTP request (unlike LocalStorage)
- **Security**: Can be made HTTP-only with `secure=True` (inaccessible to JavaScript, ideal for auth tokens)

**Example**:
```python
import reflex as rx
from datetime import datetime, timedelta

class State(rx.State):
    # Secure cookie - HTTP-only, inaccessible to JavaScript
    auth_token: str = rx.Cookie(max_age=3600, secure=True)  # Expires in 1 hour
    
    # Regular cookie
    user_id: str = rx.Cookie()
    
    # Cookie with custom settings
    session_id: str = rx.Cookie(max_age=86400, secure=True)
    
    @rx.event
    def login(self, username: str, password: str):
        # Simulate authentication
        if username and password:
            # Secure cookie - protected from XSS attacks
            self.auth_token = f"token_{username}_{datetime.now().timestamp()}"
            self.user_id = username
            self.session_id = f"session_{datetime.now().timestamp()}"
    
    @rx.event
    def logout(self):
        self.auth_token = ""
        self.user_id = ""
        self.session_id = ""

def index():
    return rx.vstack(
        rx.cond(
            State.auth_token,
            rx.vstack(
                rx.text(f"Logged in as: {State.user_id}"),
                rx.button("Logout", on_click=State.logout),
            ),
            rx.vstack(
                rx.input(id="username", placeholder="Username"),
                rx.input(id="password", type="password", placeholder="Password"),
                rx.button(
                    "Login",
                    on_click=lambda: State.login(
                        rx.get_value("username"),
                        rx.get_value("password")
                    )
                ),
            ),
        ),
    )
```

**When to use**:
- **Data frquently accessed on server side** (cookies are sent with each HTTP request)
- **User authentication** (tokens, session IDs) - use `secure=True` for auth tokens
- **Fine-grained control** over expiration and scope
- **Limit data to specific paths** in your app
- Data with expiration requirements
- **Secure storage** that needs protection from XSS attacks (use `secure=True`)

**Cookie Parameters**:
- `max_age`: Expiration time in seconds
- `secure=True`: Makes cookie HTTP-only (inaccessible to JavaScript, ideal for auth tokens)
- `path`: Limit cookie to specific paths in your app

**Cookie vs LocalStorage**:
- Cookies are sent with every HTTP request (can impact performance, but enables server access)
- LocalStorage is only accessible via JavaScript (client-side only)
- Cookies can have expiration times and path scoping
- Cookies have size limits (~4KB vs ~5MB for LocalStorage)
- Cookies can be HTTP-only with `secure=True` (not accessible via JavaScript for security)
- Use secure cookies for authentication tokens to prevent XSS attacks

## Complete Working Example

Here's a comprehensive example demonstrating all storage types:

```python
import reflex as rx
import json
from datetime import datetime

class StorageState(rx.State):
    # 1. Public State var - per tab, server memory, sent to client
    tab_counter: int = 0
    
    # 2. Private State var - per tab, server memory, server-only
    _internal_cache: dict = {}
    cache_size: int = 0  # Public var to expose cache info
    
    # 3. SessionStorage - per tab, browser storage
    session_notes: str = rx.SessionStorage()
    
    # 4. LocalStorage - per browser, persistent
    persistent_settings: str = rx.LocalStorage()
    
    # 5. LocalStorage with sync - shared across tabs
    shared_theme: str = rx.LocalStorage(sync=True, default="light")
    
    # 6. Cookie - persistent, sent with requests
    user_session: str = rx.Cookie(max_age=86400)  # 24 hours
    
    @rx.event
    def increment_counter(self):
        """Public State var - lost on server restart"""
        self.tab_counter += 1
    
    @rx.event
    def add_to_cache(self, key: str, value: str):
        """Private State var - can store any Python object"""
        self._internal_cache[key] = {"value": value, "timestamp": datetime.now()}
        self.cache_size = len(self._internal_cache)  # Update public var for UI
    
    @rx.event
    def save_session_note(self, note: str):
        """SessionStorage - lost when tab closes"""
        self.session_notes = note
    
    @rx.event
    def save_settings(self, setting_name: str, value: str):
        """LocalStorage - persists forever"""
        settings = self.get_settings()
        settings[setting_name] = value
        self.persistent_settings = json.dumps(settings)
    
    @rx.event
    def toggle_theme(self):
        """LocalStorage with sync - updates all tabs"""
        self.shared_theme = "dark" if self.shared_theme == "light" else "light"
    
    @rx.event
    def create_session(self, username: str):
        """Cookie - persists and sent with requests"""
        self.user_session = f"{username}_{datetime.now().timestamp()}"
    
    def get_settings(self) -> dict:
        if self.persistent_settings:
            return json.loads(self.persistent_settings)
        return {}

def index():
    return rx.container(
        rx.vstack(
            rx.heading("Reflex Storage Types Demo", size="lg"),
            
            # Page-only value
            rx.text(f"Page loaded at: {datetime.now().strftime('%H:%M:%S')}"),
            rx.text("☝️ This timestamp never updates (page-only value)"),
            
            rx.divider(),
            
            # Public State var
            rx.heading("Public State Variable (Per-Tab, Server Memory)", size="md"),
            rx.text(f"Counter: {StorageState.tab_counter}"),
            rx.button("Increment", on_click=StorageState.increment_counter),
            rx.text("✅ Survives page refresh | ❌ Lost on server restart | ❌ Not shared across tabs"),
            
            rx.divider(),
            
            # Private State var
            rx.heading("Private State Variable (Server-Only)", size="md"),
            rx.hstack(
                rx.input(id="cache_key", placeholder="Cache key"),
                rx.input(id="cache_value", placeholder="Cache value"),
                rx.button(
                    "Add to Cache",
                    on_click=lambda: StorageState.add_to_cache(
                        rx.get_value("cache_key"),
                        rx.get_value("cache_value")
                    )
                ),
            ),
            rx.text(f"Cache size: {StorageState.cache_size}"),
            rx.text("⚠️ Private var (_internal_cache) not visible in UI, only cache_size is shown"),
            
            rx.divider(),
            
            # SessionStorage
            rx.heading("SessionStorage (Per-Tab, Browser)", size="md"),
            rx.input(
                placeholder="Session notes",
                value=StorageState.session_notes,
                on_change=StorageState.save_session_note
            ),
            rx.text(f"Notes: {StorageState.session_notes}"),
            rx.text("✅ Survives page refresh | ✅ Survives server restart | ❌ Lost when tab closes"),
            
            rx.divider(),
            
            # LocalStorage
            rx.heading("LocalStorage (Per-Browser, Persistent)", size="md"),
            rx.hstack(
                rx.input(id="setting_name", placeholder="Setting name"),
                rx.input(id="setting_value", placeholder="Setting value"),
                rx.button(
                    "Save Setting",
                    on_click=lambda: StorageState.save_settings(
                        rx.get_value("setting_name"),
                        rx.get_value("setting_value")
                    )
                ),
            ),
            rx.text(f"Settings: {StorageState.persistent_settings}"),
            rx.text("✅ Survives everything | ⚠️ Not auto-synced across tabs"),
            
            rx.divider(),
            
            # LocalStorage with sync
            rx.heading("LocalStorage with Sync (Shared Across Tabs)", size="md"),
            rx.text(f"Current theme: {StorageState.shared_theme}"),
            rx.button("Toggle Theme", on_click=StorageState.toggle_theme),
            rx.text("✅ Survives everything | ✅ Updates all open tabs immediately"),
            
            rx.divider(),
            
            # Cookie
            rx.heading("Cookie (Persistent, Sent with Requests)", size="md"),
            rx.hstack(
                rx.input(id="username", placeholder="Username"),
                rx.button(
                    "Create Session",
                    on_click=lambda: StorageState.create_session(rx.get_value("username"))
                ),
            ),
            rx.text(f"Session: {StorageState.user_session}"),
            rx.text("✅ Survives everything | ✅ Sent with HTTP requests | ⏰ Can expire"),
            
            spacing="4",
        ),
        padding="4",
    )

app = rx.App()
app.add_page(index)
```

## Decision Tree: Which Storage Type to Use?

```
Should the data be shared across browser tabs?
│
├─ YES (Shared across tabs) → Use client-side storage
│   │
│   ├─ Need to send with HTTP requests? → Use Cookie
│   │   └─ Best for: Authentication tokens (use secure=True), session IDs
│   │   └─ Features: Sent with requests, expiration control, path scoping, HTTP-only option
│   │   └─ Note: Changes NOT synced immediately (requires page refresh)
│   │
│   └─ Client-side only? → Use LocalStorage
│       │
│       ├─ Need immediate sync across tabs? → Use LocalStorage(sync=True)
│       │   └─ Best for: User preferences, theme settings that update live
│       │   └─ Features: ~5MB storage, persists indefinitely, immediate propagation
│       │
│       └─ Shared data, refresh OK? → Use LocalStorage() or Cookie
│           └─ LocalStorage: ~5MB storage, persists indefinitely, updates on refresh
│           └─ Cookie: ~4KB storage, sent with requests, can expire, HTTP-only option
│
└─ NO (Private per tab) → Use server-side or per-tab storage
    │
    ├─ Valuable data, that should be persistent but tied to one tab → Use SessionStorage variable
    │   └─ Best for: Shopping carts, multi-step processes
    │   └─ Features: Survives server restart, cleared on tab close, isolated per tab
    │   └─ Special: Can persist long inactivity periods when Redis would clear cache by TTL
    │
    └─ Server-side state (lost on restart) → Use State variables
        │
        ├─ Need to use in UI? → Use Public State vars
        │   └─ Best for: User input, counters, displayed data
        │   └─ Requirement: Must be serializable (str, int, list, dict, etc.)
        |   └─ Actually this is the most common case.
        │
        └─ Server-only? → Use Private State vars (prefix with _)
            └─ Best for: Complex data structures, caching, sensitive data, server-side processing
            └─ Features: Picklable types, not sent to client, cannot use in UI
```

## Best Practices for AI Agents

1. **Use Public State vars for UI-visible data** - they're sent to the client and can be used in components (must be serializable).

2. **Use Private State vars (prefix with _) for server-only data** - complex data structures, caching, sensitive data that doesn't need to be in UI

3. **Default to Public State variables** for most application state - they're reactive and easy to work with

4. **Use LocalStorage for user preferences** that should persist across sessions (theme, language, etc.)

5. **Use Cookies for authentication** - they're automatically sent with requests and can expire

6. **Use SessionStorage for valuable per-tab data** that should survive page refresh/server disconnect but not tab close

7. **Always serialize complex data** when using LocalStorage/SessionStorage/Cookie:
   ```python
   # Good
   self.storage_var = json.dumps({"key": "value"})
   
   # Bad - will fail
   self.storage_var = {"key": "value"}
   ```

8. **Use `rx.LocalStorage(sync=True)` for immediate updates** across tabs (theme, notifications, etc.)

9. **Remember scope differences**:
   - Public State vars: Per-tab (each tab is independent), sent to client
   - Private State vars: Per-tab (each tab is independent), server-only
   - SessionStorage: Per-tab (each tab is independent)
   - LocalStorage: Per-browser (always shared, but sync=True needed for immediate updates)
   - Cookie: Per-browser (always shared, but sync=True needed for immediate updates)

10. **Consider data size**: Cookies have ~4KB limit, LocalStorage ~5-10MB

11. **Set appropriate expiration** for Cookies using `max_age` parameter

12. **Don't store sensitive data** in LocalStorage/SessionStorage - they're accessible via JavaScript

13. **Private vars cannot be used in UI** - if you need to display data from a private var, compute it in an event handler and store the result in a public var or use computed public variable
