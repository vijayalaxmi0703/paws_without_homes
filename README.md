# Paws Without Homes

Flask app for rescue reporting, adoption, volunteering, and donations.

## Local run

```bash
py -m pip install -r requirements.txt
py server1.py
```

Open `http://127.0.0.1:5000`

You can also use:

```bash
py start.py
```

## Notes

- `api/index.py` is the main Flask app and Vercel entrypoint.
- `server1.py` is the local runner for the same Flask app.
- `server.py` is an old legacy server and should not be used for local Flask development.
- Configure Razorpay with environment variables:

```bash
set RAZORPAY_KEY_ID=your_test_key_id
set RAZORPAY_KEY_SECRET=your_test_key_secret
```
