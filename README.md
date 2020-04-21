<p align='center'>
  <img alt="ibet" src="https://user-images.githubusercontent.com/963333/71643901-ef86e100-2d02-11ea-9185-47c06e529910.png" width="300"/>
</p>

# ibet for Issuer

<p>
  <img alt="Version" src="https://img.shields.io/badge/version-0.11-blue.svg?cacheSeconds=2592000" />
  <a href="#" target="_blank">
    <img alt="License: Apache--2.0" src="https://img.shields.io/badge/License-Apache--2.0-yellow.svg" />
  </a>
</p>


## Starting the Server
Install packages
```bash
$ cd ibet-Issuer
$ pip install -r requirements.txt
```

Generating public/private rsa key pair
```
$ python rsa/create_rsakey.py password
```

You can start the server with:
```bash
$ gunicorn -b localhost:5000 --reload manage:app --config guniconf.py
```

Or you can start a `development` server with:
```bash
$ python manage.py runserver
```


## Running the tests

You can run the tests with:
```bash:
$ python manage.py test
```

You can check the test options with:
```bash
$ python manage.py test --help
```
