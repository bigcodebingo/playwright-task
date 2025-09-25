import asyncio
from models.lolalytics_parser import LolalyticsParser
from models.deeplol_parser import DeepLOLParser
async def main():

    parser = LolalyticsParser()

    try:
        await parser.setup()
        data = await parser.parse_champion_build(champion='Jax', tier='master_plus')

        if data:
            pretty_json = data.model_dump_json(indent=2,exclude_unset=True)
            print(pretty_json)
        else:
            print("Failed to retrieve data")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        await parser.close()

if __name__ == "__main__":
    asyncio.run(main())