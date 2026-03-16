#!/usr/bin/env python3
"""Test script for dynamic enum query functionality."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from render.services.render_service import render_service
from render.services.query_executor import query_executor


async def test_enum_query():
    """Test dynamic enum query functionality."""
    print("Testing dynamic enum query functionality...\n")
    
    try:
        # Initialize query executor
        print("1. Initializing query executor...")
        await query_executor.initialize()
        print("   ✓ Query executor initialized\n")
        
        # Get metadata for simple-test report
        print("2. Getting metadata for 'simple-test' report...")
        metadata = await render_service.getReportMetadata("simple-test")
        print(f"   ✓ Loaded metadata for: {metadata.name}\n")
        
        # Display all parameters
        print("3. Report parameters:")
        for param in metadata.parameters:
            print(f"\n   Parameter: {param.name}")
            print(f"   - Type: {param.type}")
            print(f"   - Required: {param.required}")
            print(f"   - Description: {param.description}")
            
            if param.enum_query:
                print(f"   - Enum Query: {param.enum_query}")
                print(f"   - Resolved Enum Values: {param.enum}")
            elif param.enum:
                print(f"   - Static Enum Values: {param.enum}")
            
            if param.default:
                print(f"   - Default: {param.default}")
        
        print("\n" + "="*60)
        print("✓ Test completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        await query_executor.close()
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_enum_query())
    sys.exit(0 if success else 1)
