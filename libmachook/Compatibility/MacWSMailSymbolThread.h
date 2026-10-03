#pragma once
#import <Foundation/Foundation.h>
#include <dispatch/dispatch.h>
#include <pthread.h>

typedef id (*MacWSMailSymbolFunction)(id, SEL, id, NSInteger, id, id);

static inline id macws_mail_symbol_on_main_thread(
    MacWSMailSymbolFunction original, id receiver, SEL selector,
    id name, NSInteger scale, id font, id description) {
    if (pthread_main_np())
        return original(receiver, selector, name, scale, font, description);
    __block id image = nil;
    __block NSException *failure = nil;
    dispatch_sync(dispatch_get_main_queue(), ^{
        @try {
            // Transfer ownership across the main queue's autorelease pool.
            image = [original(receiver, selector, name, scale, font, description) retain];
        } @catch (NSException *exception) {
            failure = [exception retain];
        }
    });
    if (failure) @throw [failure autorelease];
    return [image autorelease];
}
