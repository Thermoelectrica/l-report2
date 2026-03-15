"""SQL query executor with parameter binding."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import asyncpg
import pandas as pd

from config import settings
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
    ) -> Dict[str, pd.DataFrame]:
        """
        Execute all SQL queries for a report.

        Args:
            report: Report object with query files
            parameters: User-provided parameters for query binding

        Returns:
            Dictionary mapping query names to DataFrames with results
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
            df = await self._execute_query(query, parameters, timeout, report.metadata)
            results[query_name] = df

            logger.info(f"Query {query_name} returned {len(df)} rows")

        return results

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
        named_params_in_query = re.findall(r":(\w+)", query)

        # If no named parameters found, assume positional parameters already
        # and use metadata order
        if not named_params_in_query:
            positional_params = []
            if metadata.parameters:
                for param_def in metadata.parameters:
                    param_name = param_def.name
                    if param_name in parameters:
                        positional_params.append(parameters[param_name])
                    elif param_def.default is not None:
                        positional_params.append(param_def.default)
                    elif not param_def.required:
                        positional_params.append(None)
            return query, positional_params

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
                value = param_def.default
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
            # Use word boundaries to avoid partial replacements
            converted_query = re.sub(
                rf":{param_name}\b", f"${position}", converted_query
            )

        return converted_query, positional_params

    async def _execute_query(
        self, query: str, parameters: Dict[str, Any], timeout: int, metadata: Any
    ) -> pd.DataFrame:
        """
        Execute a single query and return DataFrame.

        Args:
            query: SQL query string with named (:param_name) or positional ($1, $2) parameters
            parameters: Parameter values for binding (named)
            timeout: Query timeout in seconds
            metadata: Report metadata containing parameter definitions

        Returns:
            DataFrame with query results
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

                # Convert to DataFrame
                if rows:
                    columns = rows[0].keys()
                    data = [dict(row) for row in rows]
                    return pd.DataFrame(data, columns=columns)
                else:
                    return pd.DataFrame()

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
