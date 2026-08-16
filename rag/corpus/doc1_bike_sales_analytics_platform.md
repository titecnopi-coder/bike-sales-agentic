# 🚴 Bike Sales Analytics Platform

## Descripción

Proyecto de analítica de datos enfocado en ventas de bicicletas. El objetivo fue construir una solución completa de análisis utilizando Python, PostgreSQL, SQL y Power BI.

El proyecto incluye procesos de limpieza, transformación, carga de datos, consultas SQL analíticas y visualización de KPIs en un dashboard interactivo.

## Arquitectura del proyecto

CSV / Datos fuente → Python + Pandas → PostgreSQL → Power BI

## Tecnologías utilizadas

Python, Pandas, SQLAlchemy, PostgreSQL, SQL, Power BI, Git / GitHub

## Proceso realizado

- Limpieza y transformación de datos con Python y Pandas.
- Carga de datos en PostgreSQL mediante ETL.
- Desarrollo de consultas SQL analíticas.
- Creación de dashboard interactivo en Power BI.

## KPIs principales

- Ventas Totales
- Órdenes Totales
- Productos Vendidos
- Ventas por Categoría
- Top 10 Productos Más Vendidos
- Ventas por Tienda

## Databricks / Spark

Se realizó una práctica en Databricks usando Spark para cargar el dataset de ventas, revisar el esquema, transformar columnas numéricas y generar agregaciones analíticas.

Flujo: CSV → Databricks Notebook → Spark DataFrame → Limpieza de tipos de datos → Agregaciones por categoría y producto → Tabla analítica en Databricks.

Actividades: carga de CSV usando Spark DataFrames, validación de esquema y tipos de datos, limpieza y transformación de columnas numéricas, agregaciones analíticas por categoría y producto, persistencia de tabla analítica en Databricks.

## Multicloud Data Pipeline - Bike Sales Analytics

Pipeline de datos completo desde la simulación local hasta la nube real:

1. CSV local → Carpeta raw/processed (simulación de Data Lake)
2. Spark / Databricks: lectura de CSV, limpieza de columnas numéricas, agregaciones de ventas por categoría y top productos, guardado como tabla analítica en Databricks
3. AWS S3: subida de archivos raw y processed, simulación de almacenamiento cloud real
4. Power BI: conexión a CSV limpio o tabla Databricks, dashboard interactivo de ventas y KPIs

## Cloud & Multicloud

El proyecto evolucionó desde una simulación local de almacenamiento tipo Data Lake (raw/processed) hacia integración con servicios cloud reales. Se implementó almacenamiento en AWS S3 para carga automática de archivos mediante Python y boto3, junto con procesamiento distribuido usando Spark y Databricks. Adicionalmente, se exploraron conceptos de arquitectura multicloud utilizando Azure y AWS como referencia para pipelines modernos de datos y analítica.
