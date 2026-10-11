"""payment-stub: a fake payment processor that orders-api depends on.

It exists so we have a real network dependency that can be made slow or failing, which lets us
practise telling "our app is broken" apart from "something we call is broken".
"""
