set -eu

export PYTHONUNBUFFERED=true

VIRTUALENV=.data/venv

if [ ! -d $VIRTUALENV ]; then
  python3 -m venv $VIRTUALENV
fi

if [ ! -f $VIRTUALENV/bin/pip ]; then
<<<<<<< HEAD
  curl --silent --show-error --retry 5 https://bootstrap.pypa.io/pip/3.5/get-pip.py | $VIRTUALENV/bin/python3
=======
  curl --silent --show-error --retry 5 https://bootstrap.pypa.io/pip/3.5/get-pip.py | $VIRTUALENV/bin/python
>>>>>>> 6c68371f412e940a9d90a952d17e28ba990b0ca8
fi

$VIRTUALENV/bin/pip install -r requirements.txt

<<<<<<< HEAD
$VIRTUALENV/bin/python3 app.py
=======
$VIRTUALENV/bin/python3 app.py
Footer
>>>>>>> 6c68371f412e940a9d90a952d17e28ba990b0ca8
