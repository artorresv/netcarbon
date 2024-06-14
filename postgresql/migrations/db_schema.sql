-- create postgis_raster
CREATE EXTENSION IF NOT EXISTS postgis_raster SCHEMA postgis;

-- regions table
DROP table IF EXISTS public.regions;

CREATE TABLE public.regions (
  region_id           TEXT  NOT NULL CONSTRAINT regions_region_id_pk PRIMARY KEY,
  description_native  TEXT  NOT NULL,
  geom			      GEOMETRY(MultiPolygon, 2154)  NOT NULL
);

CREATE INDEX region_geom_idx ON public.regions USING gist (geom);

-- plots table
DROP TABLE IF EXISTS public.plots;

CREATE TABLE public.plots (
  id			TEXT PRIMARY KEY,
  region_id		TEXT NULL,
  last_updated	TIMESTAMP WITH TIME ZONE DEFAULT now()  NOT NULL,
  geom			GEOMETRY(MultiPolygon, 2154)  NOT NULL,
  CONSTRAINT "fk_plot_region_id_regions_region_id" FOREIGN KEY ("region_id") REFERENCES public.regions(region_id)
);

CREATE INDEX plots_geom_idx ON public.plots USING gist (geom);

-- derived products
DROP TABLE IF EXISTS public.products;

CREATE TABLE public.products (
  id			SERIAL PRIMARY KEY,
  plot_id       TEXT NOT NULL,  
  product_name	TEXT NOT NULL,
  product_date	DATE NOT NULL,
  rast 			RASTER NOT NULL,
  last_updated	TIMESTAMP WITH TIME ZONE DEFAULT now()  NOT NULL,
  CONSTRAINT "fk_products_crop_id_plots_id" FOREIGN KEY ("plot_id") REFERENCES public.plots(id)
);

-- materialized views

-- spectral indices descriptive stats
DROP MATERIALIZED VIEW IF EXISTS public.spectral_indices_stats;

CREATE MATERIALIZED VIEW public.spectral_indices_stats AS
    WITH resampled AS (
        SELECT p.id,
               pixel_stats.*
        FROM products p INNER JOIN plots ps ON p.plot_id = ps.id,
            ST_SummaryStats(
                ST_Clip(
                    ST_Rescale(p.rast, scalex := 1, scaley := 1),
                    ps.geom
                ),
                TRUE
            ) AS pixel_stats
        WHERE pixel_stats.count > 0
    )
    SELECT plot_id,
           product_name,
           product_date, 
           r.count,
           r.mean,
           r.stddev,
           r.min,
           r.max
    FROM products p INNER JOIN resampled r ON p.id = r.id
WITH DATA;

CREATE UNIQUE INDEX spectral_indices_stats_pkey ON public.spectral_indices_stats USING btree (plot_id, product_name, product_date);

-- functions

-- clip and resample an spectral index
DROP FUNCTION IF EXISTS public.Spectral_Index_Clip(TEXT, TEXT, DATE, DOUBLE PRECISION);

CREATE OR REPLACE FUNCTION public.Spectral_Index_Clip(
    _plot_id TEXT, _product_name TEXT, _product_date DATE, _target_scale FLOAT
)
RETURNS RASTER
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE STRICT
AS $$
    DECLARE
        tiff_content RASTER;
    BEGIN
        SELECT ST_Clip(
        	       ST_Rescale(
        	           p.rast,
					   scalex := _target_scale,
                       scaley := _target_scale
                   ),
				   plots.geom
			    )
	    INTO tiff_content
        FROM products p INNER JOIN plots ON p.plot_id = plots.id
        WHERE p.plot_id = _plot_id AND p.product_name = _product_name AND p.product_date = _product_date;

    RETURN tiff_content;
    END;
$$;

-- export spectral index as TIFF  
DROP FUNCTION IF EXISTS public.Spectral_Index_AsTIFF(TEXT, TEXT, DATE, DOUBLE PRECISION, INT);

CREATE OR REPLACE FUNCTION public.Spectral_Index_AsTIFF(_plot_id TEXT, _product_name TEXT,
														 _product_date DATE, _target_scale FLOAT,
														 _srid INT)
RETURNS BYTEA
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE STRICT
AS $$
    BEGIN
	    
	RETURN ST_AsTIFF(
             	Spectral_Index_Clip(_plot_id, _product_name, _product_date, _target_scale),
	            srid := _srid,
	            compression := 'LZW'
	         );
    END;
$$;

-- export spectral index as PNG
DROP FUNCTION IF EXISTS public.Spectral_Index_AsPNG(TEXT, TEXT, DATE, INT, INT);

CREATE OR REPLACE FUNCTION public.Spectral_Index_AsPNG(_plot_id TEXT, _product_name TEXT,
														 _product_date DATE, _target_scale INT,
                                                         _srid INT)
RETURNS BYTEA
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE STRICT
AS $$
	DECLARE
        tiff_content BYTEA;
    BEGIN
	    
	WITH reclassed AS (
		SELECT ST_MapAlgebra(
			       Spectral_Index_Clip(_plot_id, _product_name, _product_date, _target_scale),
				   1,
				   '8BUI',
				   'round(([rast]*1000)::numeric, 0)',
				   0
			 ) AS rast
	)
	SELECT ST_AsPNG(
               ST_Resize(
                   ST_ColorMap(rast, 1, 'bluered'),
				   '200%', '200%'
			   ),
               nband := 1,
               compression := 9
           ) INTO tiff_content
	FROM reclassed;
	    
	RETURN tiff_content;
    END;
$$;
