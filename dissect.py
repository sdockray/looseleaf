# Break apart a page into columns of text

import cv2
import copy
import numpy as np
from scipy.cluster.vq import kmeans, vq

def invert(im):
    return 255-im

def denoise(im, ksize=3):
    return cv2.medianBlur(im, ksize)

def grey(im):
    # might be better called "red"
    if len(im.shape) > 2:
        im = im.mean(axis=2).astype(np.uint8)
    return im

def adaptive_thresh(im):
    return cv2.adaptiveThreshold(im, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

def thresh(im, cutoff=30):
    return (255 * (im > cutoff)).astype(np.uint8)

def dilate(im, iterations=5):
    return cv2.dilate(im, None, iterations=iterations)

def smooth(im, shape=(40,10)):
    im = cv2.blur(im, shape)
    return thresh(im)

def contours(im):
    # c, _hierarchy = cv2.findContours(im, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c, _hierarchy = cv2.findContours(im, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return c

def wrap_contours(contours):
    return [cv2.minAreaRect(X) for X in contours]

def normalize_rect(rect):
    ((cx, cy), (w, h), rot) = rect
    if rot < -45 and w < h:
        return ((cx,cy), (h,w), rot+90)
    else:
        return rect

def merge_rects(r1, r2):
    mbox = merge_boxes([rect_to_points(X) for X in [r1,r2]])
    return (((mbox[0] + mbox[2])/2, (mbox[1] + mbox[3])/2), # (cx,cy)
            (abs(mbox[2] - mbox[0]), abs(mbox[3] - mbox[1])), # (w,h)
            0)#(r1[2] + r2[2]) / 2)                              # deg

# XXX: these should be percentages of the image size
def prune_rects(rects, min_width=200, min_height=20, max_height=200, max_width=2000):
    return filter(lambda X: X[1][0] > min_width and X[1][1] < max_height and X[1][0] < max_width and X[1][1] > min_height, rects)

def join_horizontal_rects(rects, strange_eps=20, gap_eps=60, yh_com_eps=15):#y_eps=10, h_eps=15):
    # Look at size of gap, similarity of y/h, and rarity of b1x2/b2x1 as signals
    # Look for case where `box1' is to the left of `box2'

    line_starts = np.array([X[0][0] - X[1][0]/2 for X in rects])
    line_ends = np.array([X[0][0] + X[1][0]/2 for X in rects])

    def strangeness_of(elem, arr, strange_percentage=0.05):
        # How weird is it that this element is in the array
        n_similar = sum(abs(arr - elem) < strange_eps)
        # Anything less than strange_percentage is strange.
        normalcy_cutoff = strange_percentage * len(arr)
        if n_similar < normalcy_cutoff:
            return n_similar
        return 0

    mergelist = {}              # idx (right) -> idx (left)

    for l_idx, box1 in enumerate(rects):
        p1 = rect_to_points(box1)
        for r_idx, box2 in enumerate(rects):
            if box1 == box2:
                continue
            p2 = rect_to_points(box2)

            gap_size = p2[0] - p1[2]
            if gap_size < 0 or gap_size > gap_eps:
                continue

            # y_diff = abs(box1[0][1] - box2[0][1])
            # if y_diff > y_eps:
            #     continue
            # h_diff = abs(box1[1][1] - box2[1][1])
            # if h_diff > h_eps:
            #     continue
            y_diff = abs(box1[0][1] - box2[0][1])
            h_diff = abs(box1[1][1] - box2[1][1])
            if y_diff + h_diff > yh_com_eps:
                continue

            b1x2_strange = strangeness_of(p1[2], line_ends)
            b2x1_strange = strangeness_of(p2[0], line_starts)

            if b1x2_strange > 0 and b2x1_strange > 0:
                # merge!
                mergelist[r_idx] = l_idx
                break
                

    # Do the merge
    mutable_rects = copy.deepcopy(rects) # I think deepcopy is not necessary(?)
    for idx, rect in enumerate(mutable_rects):
        if idx in mergelist:    # Merge left
            cur_idx = idx
            left_rect = None
            # Find rect to merge with (old one may have been deleted)
            while left_rect is None:
                cur_idx = mergelist[cur_idx]
                left_rect = mutable_rects[cur_idx]

            mutable_rects[cur_idx] = merge_rects(rect, left_rect)
            mutable_rects[idx] = None
    return filter(lambda x: x is not None, mutable_rects)

def draw_rects(im, rects, color=(0,0,255), thickness=3):
    for r in rects:
        box = np.int32(cv2.cv.BoxPoints(r)).reshape((-1,1,2))
        cv2.drawContours(im, [box], 0, color, thickness)

def cluster_columns(features, k):
    codebook, distortion = kmeans(features, k)
    clusters, distance = vq(features, codebook)

    print "For K=%d, distortion is %f and sum distance is %f" % (k, distortion, sum(distance))

    return {"codebook": codebook,
            "distortion": distortion,
            "clusters": clusters,
            "distance": distance}

def multicluster_columns(rects, min_clusters=1, max_clusters=20):
    # Assumes rects have been normalized
    # XXX: assume rotation is negligible

    # Our feature vector is (cx, cy, w)
    # features = np.array([(X[0][0], X[0][1], X[1][0]) for X in rects])
    # features = np.array([(X[0][0], X[1][0]) for X in rects])
    # features = np.array([(X[0][1], X[1][0]) for X in rects])
    # features = np.array([X[1] for X in rects])

    # x1, x2
    # features = np.array([(X[0][0] - X[1][0]/2, X[0][0] + X[1][0]/2) for X in rects])

    # x1,x2,cy
    features = np.array([(X[0][0] - X[1][0]/2, X[0][0] + X[1][0]/2, X[0][1]) for X in rects])

    res = []

    for k in range(min_clusters, max_clusters): # XXX: not inclusive
        res.append(cluster_columns(features, k))

    return res

def random_color():
    return (255*np.random.random(3)).astype(np.uint8).tolist()

def draw_clusters(im, rects, clusters):
    nclusters = clusters.max() + 1
    colors = [random_color() for _X in range(nclusters)]
    for idx in range(nclusters):
        cluster_rects = np.array(rects)[clusters==idx]
        cluster_rects = [tuple(x) for x in cluster_rects]
        draw_rects(im, cluster_rects, color=colors[idx])

def merge_boxes(boxes):
    if len(boxes) == 0:
        return []
    boundings = np.array(boxes)
    return (boundings[:,0].min(), boundings[:,1].min(), 
            boundings[:,2].max(), boundings[:,3].max())

def rect_to_points(X):
    return [X[0][0] - X[1][0]/2,
            X[0][1] - X[1][1]/2,
            X[0][0] + X[1][0]/2,
            X[0][1] + X[1][1]/2]

def bound_rects(rects):
    return merge_boxes([rect_to_points(X) for X in rects])

def draw_boxes(im, boxes):
    for box in boxes:
        cv2.drawContours(im, [np.int32(box).reshape((-1,1,2))], 0, random_color(), 4)

def prune_clusters(rects, clusters, min_lines=3):
    good_indices = np.zeros(len(clusters), dtype=np.bool)
    for c_idx in set(clusters.tolist()):
        if sum(clusters == c_idx) >= min_lines:
            good_indices[clusters == c_idx] = True

    good_rects = np.array(rects)[good_indices].tolist()
    good_clusters = clusters[good_indices]
    return (good_rects, good_clusters)
    

def bound_clusters(rects, clusters):
    return [bound_rects(np.array(rects)[clusters == X]) for X in set(clusters.tolist())]

def join_boxes(boxes, x_eps=100, y_eps=150, w_eps=100):
    for box1 in boxes:
        for box2 in boxes:
            if box1 == box2:
                continue
            # Check distance between b1x1 and b2x1, as well as b1y2 and b2y1 and the respective widths
            b1w = box1[2]-box1[0]
            b2w = box2[2]-box2[0]
            # When checking y-closeness, allow for box2 to overlap box1
            box2_starts_after = box2[1] > box1[1]

            if abs(box1[0] - box2[0]) < x_eps and box2_starts_after and box2[1] - box1[3] < y_eps and abs(b1w - b2w) < w_eps:
                box3 = merge_boxes([box1, box2])
                # Python lacks tail-recursion, duh!
                return join_boxes(filter(lambda x: x != box1 and x != box2, boxes) + [box3],
                                  x_eps=x_eps, y_eps=y_eps, w_eps=w_eps)
    # Done!
    return boxes

def prune_boxes(boxes):
    # another stupid pruning that looks for boxes in boxes
    hitlist = []
    outboxes = list(boxes)
    for box1 in boxes:
        for box2 in boxes:
            if box1 == box2:
                continue
            # is box2 in box1?
            if box2[0] > box1[0] and box2[1] > box1[1] and box2[2] < box1[2] and box2[3] < box1[3]:
                # it is!
                if box2 in outboxes:
                    # n^3!
                    outboxes.remove(box2)
    return outboxes

def load_image(path_to_image):
    return cv2.imread(path_to_image, 0) # greyscale

def rotate_image(im, eps=0.1):
    # Analyze lines to guess rotation
    thresholded = invert(adaptive_thresh(denoise(im)))
    smoothed = smooth(thresholded)
    lines = wrap_contours(contours(smoothed))
    lines = [normalize_rect(X) for X in lines]

    angles = np.array([X[2] for X in lines])
    angle = np.median(angles)

    if abs(angle) < eps:
        return im

    # Thanks! http://stackoverflow.com/questions/9041681/opencv-python-rotate-image-by-x-degrees-around-specific-point
    print "Rotating image by %f degrees" % (angle)
    center = tuple(np.array(im.shape)/2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    im = cv2.warpAffine(im, rotation_matrix, (im.shape[1], im.shape[0]),flags=cv2.INTER_LINEAR)

    # Calculate how much to crop off each side
    rads = np.deg2rad(angle)
    tan = np.arctan(rads)
    crop_x = abs(int(np.ceil(im.shape[0] * tan)))
    crop_y = abs(int(np.ceil(im.shape[1] * tan)))

    return im[crop_y:-crop_y,crop_x:-crop_x]
        

def find_columns(im):
    im = rotate_image(im)

    thresholded = invert(adaptive_thresh(denoise(im)))
    smoothed = smooth(thresholded)
    sm_ret = smoothed.copy()
    lines = wrap_contours(contours(smoothed))
    lines = [normalize_rect(X) for X in lines]

    lines = join_horizontal_rects(lines)

    lines = prune_rects(lines, min_width=im.shape[1]/5, max_width=0.9*im.shape[1])

    features = np.array([(X[0][0] - X[1][0]/2, X[0][0] + X[1][0]/2, X[0][1]) for X in lines])

    # cluster_options = multicluster_columns(lines)
    # clusters = cluster_options[-1]["clusters"]
    clusters = cluster_columns(features, 25)["clusters"]

    # lines, clusters = prune_clusters(lines, clusters)

    # Make an image that shows what's happening
    p_im = np.zeros((im.shape[0],im.shape[1],3), dtype=np.uint8)
    # Fill on all color channels
    p_im[:] = im.reshape((im.shape[0],im.shape[1],1))
    draw_clusters(p_im, lines, clusters)

    boxes = bound_clusters(lines, clusters)
    boxes = join_boxes(boxes, x_eps=im.shape[1]/10, w_eps=im.shape[1]/10)

    boxes = prune_boxes(boxes)

    draw_boxes(p_im, boxes)

    return im, thresholded, sm_ret, p_im, boxes

# draw_rects(d2, wrap_contours(contours((smooth(invert(thresh(im4)), shape=(40,10), cutoff=30)))))
