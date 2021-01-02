from tqdm import tqdm
import logging
import time
logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("Start print log")
if __name__ == '__main__':
    pbar = tqdm(total=100)
    for i in range(10):
        time.sleep(0.1)
        print(pbar.n)
        pbar.update(10)
    pbar.close()
