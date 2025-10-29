#!/bin/bash
# Script to set environment variables for Cloud Run service

echo "Setting environment variables for ninja-tutor-backend..."
echo ""

# Set the variables one by one to avoid syntax errors
gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    FIREBASE_PROJECT_ID=ninja-tutor-44dec

gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    FIREBASE_PRIVATE_KEY_ID=4f03d1eb14eb54f76bd4b4b991f5768df41e2399

gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --set-env-vars \
    FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDra6HICn1FsWaB\nbujMzdd9R9sTU4YxBymVyuzBu4N+R/zYJ4VG/tsqjsCP1KoqwUUum1XHrUulSj/g\nUpjjqR4xe7i5XbhH9ACU7eEktnZBeJ86ud8KzqjErhS4L9qxecTYigaVRLlqXzwp\nB9BWWxfPtock3tFxMH2Ad17EcltGLLCebvQyc5W35pBUnRv8U3t8PFE9h+YcvOwW\nbe1muUrU+dQlju+Ikb8gzMxBr1LCd3FM9uF7awDYlfE+LsFzyeFWD2dcz2+am4x4\nOZlb8kRNrPBDUAgJ/OPvy8NJI01fYF2JKSMUM/fbbf1DqBxKfQ/O5+vMnKLnzJii\nqKPUjXR9AgMBAAECggEABiXj7jTz64+D9UpfswWHJKLtQjZysTIWMG7Buxd6CiC4\nJi72CJIcSCK9PaRYo1AzzdFJrrLEYHctbt7JVlyyyKkJ/HFJoDtrjngd4pcPRItx\nYRe8juwxtR00tlCtnefnr53/KQPH8dK13/5vvumXGBoUsm5NOu8AwAueAnRYFN+G\nE0wAigIr0Up09tuV+N4DWjUcg9WSliprMcW5esK1pCHRfR6mBAcuQjSfkwD0jUeI\nzPmZ9LFKbrytMDQotH2yum1Toz/LFEcbjMSLgOC4q210zuc1mWvH6sXt34erW1W1\n13Od4cEm7nd5dQAKa0Q9iVg3IiTi9DgFxlf8J0KVAwKBgQD84JnQAinuDZTjv3er\nQnuxdTz8rxtkuRMpF94tGBK+O/x3vT6xMAA8s6568DTSZRuQClI9S324BMmmr6vW\n6gr5jVkmFLcgdxNQBOzO0GC32PvhThKqtub1YNMTIfxVJuyiEgCmWBLK7KiljCzh\nMikTNGms4yk83wux6Rn0swf3HwKBgQDuU9ibLNDl5Q+/YdWEZvrU/PsvBVLwkE+W\niqbl2mbFAvh7TeSHPPEyC8MIwTUqGUnrNKwhadnSImJT2SxAEsWtp6W3lc9qk1AF\nbMd6YkB4nVuKTgK68JuHHkni3Y3lJh5yhdKnweIZ6zHyTsc6TRrNn7DOTUpAGc8J\nhXdGnXws4wKBgQDQH0I4Ui+UPxVVRBYHm5YV/XmONcgD49aDMaOn1XJHozMskVJx\nniHz06Y8hEnVB2Xh7Ly2udTkiPw19csl/EXAEbdXgiEd1SLN7t+/bvzLEwhq7Eis\nvA/l0CSoUIZOxtRmpw5l2YLOBGzgozekuBXaOn7mzab49FG5wTGdlWNu3QKBgG5j\n/+zAcXJLC2RGWLQfTwfgtigteyFadsLwLiZBZ2DR426ZwcSygbYApLIlbA637/k2\nSJShhvdCXfEgotJ63310Ldo/VfezjFk27Z7Oa7ZyjLgfMjyMvj1z1h1zKgp+AZRi\nUBTMRYJj4pqtyrJCjKu50Bd+zWmriq6KV5kp0R6pAoGBAPJUldTTrWHNUzws5ioL\nGeTKhtDQhk641SeiVFamQ0ZX4/of0OV7CaUbMqOTcXkUZyKCQQWUevqiV6Xv4qRP\nev+oVYN3RbfKOTCx5WcoGOjVhX1/NEp9Ok+TWcPAsGnO9eeMh2Kqt9wtRplIEsYS\n4VjEwHP9pnlltk6OBTKkjzBp\n-----END PRIVATE KEY-----\n"

gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    FIREBASE_CLIENT_EMAIL=firebase-adminsdk-fbsvc@ninja-tutor-44dec.iam.gserviceaccount.com

gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    FIREBASE_CLIENT_ID=103740625954720621015

gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    OPENAI_API_KEY=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

gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    GOOGLE_API_KEY=AIzaSyCT4mZApp_eWfl5B3DzU-HqI9Spv6WzLYQ

gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    DEBUG=false

gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    LOG_LEVEL=INFO

gcloud run services update ninja-tutor-backend \
  --region us-central1 \
  --update-env-vars \
    FIREBASE_HOSTING_URL=ninja-tutor-44dec.web.app

echo ""
echo "✅ Environment variables set successfully!"

