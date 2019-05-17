import click

from web_crawler import WebCrawler

@click.command()
@click.argument("url", type=click.STRING)
@click.argument('depth',  type=click.INT, default=1)
@click.option('output_dir', '--output-dir', default=None, type=click.STRING)
@click.option('us_cache', '--us-cache', default=True, type=click.BOOL)
def main(url, depth, output_dir, us_cache):
    WebCrawler(url, depth=depth, output_dir=output_dir, us_cache=us_cache).run()

if __name__ == "__main__":
    main()
    # try:
    #     main()
    # except Exception as e:
    #     print "WebCrawler crached"
    #     raise e