"""SQL query executor with parameter binding."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import asyncpg

from ..config import settings
from ..models import ParameterType
from .repository import Report

logger = logging.getLogger(__name__)


class QueryExecutor:
    """Execute SQL queries against data database."""

    def __init__(self):
        self.pool: asyncpg.Pool | None = None

    async def initialize(self):
        """Create connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                host=settings.data_db_host,
                port=settings.data_db_port,
                database=settings.data_db_name,
                user=settings.data_db_user,
                password=settings.data_db_password,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            logger.info("Query executor initialized with connection pool")
        except Exception as e:
            logger.error(f"Failed to initialize query executor: {e}")
            raise

    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Query executor connection pool closed")

    async def execute_queries(
        self, report: Report, parameters: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Execute all SQL queries for a report.

        Args:
            report: Report object with query files
            parameters: User-provided parameters for query binding

        Returns:
            Dictionary mapping query names to list of row dictionaries
        """
        if not self.pool:
            raise RuntimeError(
                "Query executor not initialized. Call initialize() first."
            )

        results = {}

        for query_file in report.query_files:
            query_name = query_file.stem  # filename without extension

            # Read query
            with open(query_file, "r", encoding="utf-8") as f:
                query = f.read()

            logger.info(f"Executing query: {query_name} for report: {report.id}")

            # Execute query
            timeout = report.metadata.timeout or settings.default_query_timeout
            rows = await self._execute_query(
                query, parameters, timeout, report.metadata
            )
            results[query_name] = rows

            logger.info(f"Query {query_name} returned {len(rows)} rows")

        return results

    async def execute_enum_query(
        self, query_file: Path, parameters: Dict[str, Any] | None = None
    ) -> List[Any]:
        """
        Execute a SQL query to fetch enum values.

        Args:
            query_file: Path to SQL query file
            parameters: Optional parameters for query binding

        Returns:
            List of values from the first column of query results
        """
        if not self.pool:
            raise RuntimeError(
                "Query executor not initialized. Call initialize() first."
            )

        # Read query
        with open(query_file, "r", encoding="utf-8") as f:
            query = f.read()

        logger.info(f"Executing enum query: {query_file.name}")

        # Execute query with a short timeout (enum queries should be fast)
        timeout = 10  # 10 seconds for enum queries

        async with self.pool.acquire() as conn:
            try:
                # Set statement timeout
                await conn.execute(f"SET statement_timeout = {timeout * 1000}")

                # Execute query (enum queries typically don't need parameters)
                if parameters:
                    # Convert named parameters to positional if needed
                    # For enum queries, we create a minimal metadata object
                    from ..models import ReportMetadata

                    minimal_metadata = ReportMetadata(
                        id="enum", name="enum", format="weasyprint", parameters=[]
                    )
                    converted_query, positional_params = (
                        self._convert_named_to_positional(
                            query, parameters, minimal_metadata
                        )
                    )
                    rows = await conn.fetch(converted_query, *positional_params)
                else:
                    rows = await conn.fetch(query)

                # Extract first column values
                if rows:
                    # Get the first column name
                    first_column = list(rows[0].keys())[0]
                    return [row[first_column] for row in rows]
                else:
                    return []

            except asyncpg.QueryCanceledError:
                logger.error(f"Enum query execution timeout after {timeout} seconds")
                raise TimeoutError(f"Enum query execution exceeded {timeout} seconds")
            except asyncpg.PostgresError as e:
                logger.error(f"Database error in enum query: {e}")
                raise RuntimeError(f"Enum query execution failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error during enum query execution: {e}")
                raise

    def _convert_default_value(self, value: Any, param_type: ParameterType) -> Any:
        """
        Convert default value from metadata to proper Python type.

        Args:
            value: Default value from metadata (usually a string)
            param_type: Parameter type definition

        Returns:
            Properly typed value
        """
        if value is None:
            return None

        # If already the correct type, return as-is
        if param_type == ParameterType.STRING:
            return str(value)
        elif param_type == ParameterType.INTEGER:
            return int(value) if not isinstance(value, int) else value
        elif param_type == ParameterType.FLOAT:
            return float(value) if not isinstance(value, float) else value
        elif param_type == ParameterType.BOOLEAN:
            if isinstance(value, bool):
                return value
            # Convert string to boolean
            return str(value).lower() in ("true", "1", "yes", "on")
        elif param_type == ParameterType.DATE:
            if isinstance(value, str):
                return datetime.strptime(value, "%Y-%m-%d").date()
            return value
        elif param_type == ParameterType.DATETIME:
            if isinstance(value, str):
                # Try different datetime formats
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue
                raise ValueError(f"Unable to parse datetime: {value}")
            return value

        return value

    def _convert_named_to_positional(
        self, query: str, parameters: Dict[str, Any], metadata: Any
    ) -> Tuple[str, List[Any]]:
        """
        Convert named parameters (:param_name) to positional ($1, $2, etc.).

        Args:
            query: SQL query with named parameters (e.g., :schema_name, :table_name)
            parameters: Dictionary of parameter values
            metadata: Report metadata containing parameter definitions

        Returns:
            Tuple of (converted_query, positional_params_list)
        """
        # Find all named parameters in the query (e.g., :schema_name)
        # Exclude PostgreSQL type casts (::type) by using negative lookbehind
        named_params_in_query = re.findall(r"(?<!:):(\w+)", query)

        # If no named parameters found, return query as-is with no parameters
        if not named_params_in_query:
            return query, []

        # Build parameter mapping and values list
        param_mapping = {}  # Maps parameter name to position number
        positional_params = []

        # Process parameters in the order they appear in the query
        seen_params = set()
        for param_name in named_params_in_query:
            if param_name in seen_params:
                continue
            seen_params.add(param_name)

            # Find parameter definition in metadata
            param_def = None
            if metadata.parameters:
                for p in metadata.parameters:
                    if p.name == param_name:
                        param_def = p
                        break

            # Get parameter value
            if param_name in parameters:
                value = parameters[param_name]
            elif param_def and param_def.default is not None:
                # Convert default value to proper type
                value = self._convert_default_value(param_def.default, param_def.type)
            elif param_def and not param_def.required:
                value = None
            else:
                raise ValueError(f"Required parameter '{param_name}' not provided")

            # Add to positional params and mapping
            position = len(positional_params) + 1
            param_mapping[param_name] = position
            positional_params.append(value)

        # Replace named parameters with positional ones
        converted_query = query
        for param_name, position in param_mapping.items():
            # Use word boundaries and negative lookbehind to avoid partial replacements
            # and PostgreSQL type casts (::type)
            converted_query = re.sub(
                rf"(?<!:):{param_name}\b", f"${position}", converted_query
            )

        return converted_query, positional_params

    async def _execute_query(
        self, query: str, parameters: Dict[str, Any], timeout: int, metadata: Any
    ) -> List[Dict[str, Any]]:
        """
        Execute a single query and return list of dictionaries.

        Args:
            query: SQL query string with named (:param_name) or positional ($1, $2) parameters
            parameters: Parameter values for binding (named)
            timeout: Query timeout in seconds
            metadata: Report metadata containing parameter definitions

        Returns:
            List of dictionaries with query results (NULL values are None)
        """
        async with self.pool.acquire() as conn:
            try:
                # Set statement timeout
                await conn.execute(f"SET statement_timeout = {timeout * 1000}")

                # Convert named parameters to positional if needed
                converted_query, positional_params = self._convert_named_to_positional(
                    query, parameters, metadata
                )

                # Execute query with positional parameters
                rows = await conn.fetch(converted_query, *positional_params)

                # Convert to list of dicts (asyncpg already converts NULL to None)
                return [dict(row) for row in rows]

            except asyncpg.QueryCanceledError:
                logger.error(f"Query execution timeout after {timeout} seconds")
                raise TimeoutError(f"Query execution exceeded {timeout} seconds")
            except asyncpg.PostgresError as e:
                logger.error(f"Database error: {e}")
                raise RuntimeError(f"Query execution failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error during query execution: {e}")
                raise


# Global query executor instance
query_executor = QueryExecutor()

