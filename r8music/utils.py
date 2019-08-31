def fuzzy_groupby(iterable, threshold, key=lambda x: x):
    iterator = iter(iterable)
    item = next(iterator)
    
    def group():
        nonlocal item
        group_continues = True
        
        while group_continues:
            yield item
            
            previous_item, item \
                = item, next(iterator, None)
            
            group_continues = item and abs(key(item) - key(previous_item)) <= threshold
    
    try:
        while item:
            yield key(item), group()
    
    except StopIteration:
        pass