#Yo dawg I heard you like decorating so I made some decorators to 
#decorate your decorators into decorators

def basic_decorator(decorator):
    """Turns a given function (`decorator`) into a decorator. This function
    takes one argument (`f`), which is the function to be decorated.
    
    `f` can be called with any additional arguments that the decorator wants
    to provide, which will be given to `f` before the arguments given by the
    caller of the decorated `f`.
    
    some_value = 1
    
    @basic_decorator
    def my_decorator(f):
        ... things involving f(some_value) ...
        
    @my_decorator
    def f(some_value, arg):
        print(some_value, arg)
    
    #Prints "1 2"
    f(2)"""

    def decorated_decorator(f):
        def decorated_f(*f_args, **f_kwargs):
            call_f = lambda *extra_f_args: f(*(extra_f_args + f_args), **f_kwargs)
            return decorator(call_f)
        
        decorated_f.__name__ = f.__name__
        return decorated_f
    
    decorated_decorator.__name__ = decorator.__name__
    return decorated_decorator

@basic_decorator
def decorator_with_args(decorator):
    """Extending basic_decorator, here the given `decorator` function takes
    its own arguments after the `f` that is to be decorated.
    
    @decorator_with_args
    def maporator(f, *args):
        for arg in args:
            f(arg)
            
    @maporator(1, 2, 3)
    def f(n, m):
        print(n+m)
    
    #Prints "3\n4\n5"
    f(2)"""

    @basic_decorator
    def decorated_decorator(f):
        return decorator(f)
        
    return decorated_decorator
