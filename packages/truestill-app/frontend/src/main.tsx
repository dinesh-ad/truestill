/**
 * The React entry point. Mounts nothing yet - the first island lands next.
 *
 * What it does do is publish the hash of the sources it was built from, which is what
 * `test_the_served_bundle_was_built_from_these_sources` compares against. That test is the whole
 * proof of this seam: it can only pass if the toolchain built, the bundle was written where
 * Starlette serves it, the page loaded it as a module, and the browser executed it.
 */
declare const __BUNDLE_SOURCE_HASH__: string;

document.documentElement.dataset.bundle = __BUNDLE_SOURCE_HASH__;
